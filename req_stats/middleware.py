from asyncio.log import logger
import logging
import time
from contextlib import ExitStack
import traceback
from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed
from django.db import connections
from rest_framework.status import is_client_error, is_server_error


QUERY_COUNT = "db_query_count"
QUERY_TIME = "db_query_time_ms"
REQUEST_TIME = "duration_ms"
ALL_QUERY_DETAILS = "db_query_details"

class QueryStats:
    def __init__(self, track_details=False):
        self.query_durations = []
        self.queries = dict()
        self.track_details = track_details

    def __call__(self, execute, sql, params, many, context):
        start = time.monotonic()
        try:
            if self.track_details:
                stack_str = "".join(traceback.format_stack())
                query_details = self.queries.get(sql, SimpleNamespace(total_number=0, stacks={}))
                query_details.total_number += 1
                stack_count = query_details.stacks.get(stack_str, 0)
                query_details.stacks[stack_str] = stack_count + 1
                self.queries[sql] = query_details

            return execute(sql, params, many, context)
        finally:
            duration = time.monotonic() - start
            self.query_durations.append(duration)

    def query_count(self):
        return len(self.query_durations)

    def all_queries(self):
        return self.queries

    def total_duration(self):
        total = 0.0
        for duration in self.query_durations:
            total += duration * 1000
        return round(total, 3)


class Metrics:
    def __init__(self, initial=None):
        self._metrics = initial
        if not initial:
            self._metrics = {}
        self.LOGGABLE_METRICS = {QUERY_COUNT, QUERY_TIME, REQUEST_TIME}

    def put(self, key, value):
        self._metrics[key] = value

    def get(self, key):
        return self._metrics[key]

    def get_all(self):
        return self._metrics

    def as_log_string(self):
        metrics = [
            f"{k}={v}" for k, v in sorted(self._metrics.items()) if k in self.LOGGABLE_METRICS
        ]

        return ", ".join(metrics)


class RequestLoggingMiddleware:
    """Intercept all requests and log them, to the configured logger, at the configured level.
    PDU_REQUEST_LOGGER is the logger to use (def root logger) PDU_REQUEST_LOG_LEVEL
    is the level to use (def INFO for 2XX & 3XX, WARNING for 4XX, ERROR for 5XX).
    """

    ROOT_LOGGER = logging.getLogger(None)  # type: logging.Logger

    def __init__(self, get_response: callable) -> None:
        """Initialize the middleware and configure the logger and level.
        :type get_response: object
        """
        rlm_class = RequestLoggingMiddleware

        self.detailed_db_query_diagnostics_active = getattr(
            settings, "REQUEST_LOGGING_DETAILED_DB_QUERY_DIAGNOSTICS_ACTIVE", True
        )
        self.detailed_db_query_diagnostics_threshold = getattr(
            settings, "REQUEST_LOGGING_DETAILED_DB_QUERY_DIAGNOSTICS_THRESHOLD", 0
        )

        self.get_response = get_response  # type: callable
        self._level = getattr(settings, "PDU_REQUEST_LOG_LEVEL", logging.INFO)  # type: int
        self._logger = getattr(
            settings, "PDU_REQUEST_LOGGER", rlm_class.ROOT_LOGGER
        )  # type: logging.Logger

        print(f"logger is {self._logger}")

        self.is_active = getattr(settings, "PDU_REQUEST_LOGGING_ACTIVE", True)
        rlm_class.ROOT_LOGGER.warning(
            "RequestLoggingMiddleware start: Log level = %r, Logger = %r, Is active = %r",
            self._level,
            self._logger.name,
            self.is_active,
        )

        if not self.is_active:
            # From the django documentation:
            #   It’s sometimes useful to determine at startup time whether a piece of middleware
            #   should be used. In these cases, your middleware’s __init__() method may raise
            #   MiddlewareNotUsed. Django will then remove that middleware from the middleware
            #   process and log a debug message to the django.request logger when DEBUG is True
            raise MiddlewareNotUsed

    def __call__(self, request):
        metrics, response = self._get_response(request)

        if not self.is_active:  # pragma: no cover
            # This should not happen in practice, but it is a backstop
            return response

        status_code = self._get_status_code(response)

        self.do_logging(
            request,
            status_code,
            metrics,
            response.get("Content-Type"),
        )

        return response

    def _get_status_code(self, response):
        if hasattr(response, "status_code"):
            # `HttpResponse` has a `status_code`
            status_code = response.status_code
        else:  # pragma: no cover
            self._logger.warning(
                "Request Logger: Could not find status code in response %r", response
            )
            status_code = None

        return status_code

    def _get_response(self, request):
        metrics = Metrics()
        start_time = time.monotonic()
        if getattr(settings, "DB_INSTRUMENTATION_ENABLED", True):
            query_stats = QueryStats(track_details=self.detailed_db_query_diagnostics_active)
            with ExitStack() as stack:
                for conn in connections.all():
                    stack.enter_context(conn.execute_wrapper(query_stats))
                response = self.get_response(request)
            metrics.put(QUERY_COUNT, query_stats.query_count())
            metrics.put(QUERY_TIME, query_stats.total_duration())
            metrics.put(ALL_QUERY_DETAILS, query_stats.all_queries())
        else:
            response = self.get_response(request)
        elapsed_time_ms = (time.monotonic() - start_time) * 1000
        request_time_ms = round(elapsed_time_ms, 2)
        metrics.put(REQUEST_TIME, request_time_ms)
        return metrics, response

    def _get_level(self, status_code: int):
        if self._level:
            return self._level

        if status_code >= 500:
            return logging.ERROR
        elif status_code >= 400:
            return logging.WARNING
        else:
            return logging.INFO

    def do_logging(
        self,
        request,
        status_code,
        metrics,
        response_content_type,
    ):
        log_dict = self.parse_log(request, status_code)
        log_dict.update(metrics.get_all())
        log_dict["response_content_type"] = response_content_type
        log_msg_fragments = [
            (
                f"Received request {log_dict['request_method']} {log_dict['uri']},"
                f" status {log_dict['status']}"
            ),
            metrics.as_log_string(),
        ]
        log_msg = ", ".join(log_msg_fragments)
        self._logger.log(self._get_level(status_code), log_msg, extra=log_dict)

        if self.detailed_db_query_diagnostics_active:
            self._logger.log(self._get_level(status_code), "Detailed DB query info:")
            all_queries = metrics.get(ALL_QUERY_DETAILS)
            if all_queries:
                for key, value in sorted(
                    all_queries.items(), key=lambda x: x[1].total_number, reverse=True
                ):
                    if value.total_number > self.detailed_db_query_diagnostics_threshold:
                        self._logger.log(
                            self._get_level(status_code),
                            f"{value.total_number} instances of the following query:\n{key}",
                        )
                        for stack, num_q in sorted(
                            value.stacks.items(), key=lambda x: x[1], reverse=True
                        ):
                            self._logger.log(
                                self._get_level(status_code),
                                f"This code location accounted for {num_q} queries:",
                            )
                            self._logger.log(self._get_level(status_code), stack)


    def parse_log(self, request, status_code):
        resp_env = request.__dict__["environ"]  # type: dict
        resolver_match = request.__dict__["resolver_match"]
        log_dict = {}
        log_dict.update(
            {
                "content_type": request.content_type,
                "status": status_code,
            }
        )
        if resp_env:
            log_dict.update(
                {
                    "http_host": resp_env.get("HTTP_HOST"),
                    "protocol": resp_env.get("SERVER_PROTOCOL"),
                    "query_string": resp_env.get("QUERY_STRING"),
                    "raw_uri": resp_env.get("RAW_URI"),
                    "remote_address": resp_env.get("REMOTE_ADDR"),
                    "remote_port": resp_env.get("REMOTE_PORT"),
                    "request_method": resp_env.get("REQUEST_METHOD", "Unknown method"),
                    "server_name": resp_env.get("SERVER_NAME"),
                    "server_port": resp_env.get("SERVER_PORT"),
                    "server_version": resp_env.get("SERVER_SOFTWARE"),
                    "user_agent": resp_env.get("HTTP_USER_AGENT"),
                    "uri": resp_env.get("PATH_INFO", "Unknown URL"),
                }
            )
        if resolver_match:
            resp_resolver = resolver_match.__dict__
            log_dict.update(
                {
                    "app_names": resp_resolver.get("app_names"),
                    "namespaces": resp_resolver.get("namespaces"),
                    "resolver_function": str(resp_resolver.get("func")),
                    "route": resp_resolver.get("route"),
                    "url_name": resp_resolver.get("url_name"),
                }
            )
        return log_dict

