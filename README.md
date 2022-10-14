This project contains:
* [A reference implementation of Django middleware](req_stats/middleware.py) that allows to track your database queries within a request
  * It is self-sufficient for use in other projects, just drop it in and register.  
  * DB_INSTRUMENTATION_ENABLED controls whether DB queries are counted and time is measured, default is True
  * REQUEST_LOGGING_DETAILED_DB_QUERY_DIAGNOSTICS_ACTIVE controls whether detailed query diagnostics with call stacks is enabled, default is False
  * REQUEST_LOGGING_DETAILED_DB_QUERY_DIAGNOSTICS_THRESHOLD controls above what number of repeats a query will be logged, default is 0
* An example "library" app that can be run to demonstrate:
  * how excessive queries can happen
  * how they can be tracked

Instructions:
* Create a fresh Py 3.9.10 virtual environment (other Python versions can work but not guaranteed)
* install requirements with `pip install -r requirements.txt`
* run migrations `python manage.py migrate`
* run the server `python manage.py runserver`
* create a superuser `python manage.py createsuperuser`
* go to admin panel http://localhost:8000/admin/ and add some authors, books and physical books
* go to the book list endpoint http://127.0.0.1:8000/library/books/ and observe high level logged request stats
* by default, detailed logging it turned off via `REQUEST_LOGGING_DETAILED_DB_QUERY_DIAGNOSTICS_ACTIVE` being False in [lib_example/settings.py](lib_example/settings.py), switch that to True and rerun the list GET to observe the call stacks being reported.

There is an upcoming blog post that will describe the problem and this solution in detail, at which time the reference to the post will be inserted here.
