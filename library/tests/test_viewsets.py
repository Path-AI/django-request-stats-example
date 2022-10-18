from library.models import Author, Book
import pytest
from rest_framework.test import APIClient

@pytest.mark.django_db
class TestBookViewset:
    @pytest.fixture
    def book(self):
        return Book.objects.create(title='Grest book', author=Author.objects.create(name='Great Author'))
    
    def test_books(self, book, django_assert_max_num_queries):
        with django_assert_max_num_queries(5):
            api_client = APIClient()
            response = api_client.get(path="/library/books/")

