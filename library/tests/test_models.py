from datetime import datetime
from library.models import Author, Book, PhysicalBook
import pytest

@pytest.mark.django_db
class TestBook:
    @pytest.fixture
    def book(self):
        return Book.objects.create(title='Grest book', author=Author.objects.create(name='Great Author'))

    @pytest.fixture
    def physical_book(self, book):
        return PhysicalBook.objects.create(book=book)
    
    def test_book(self, book):
        breakpoint()
        assert book is not None

    def test_phys_book(self, physical_book):
        assert physical_book.book.num_copies_available == 1
        physical_book.borrowed_at = datetime.now()
        physical_book.save()
        physical_book.book.refresh_from_db()
        assert physical_book.book.num_copies_available == 0