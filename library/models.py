from django.db import models


class Author(models.Model):
    name = models.TextField()

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    title = models.TextField()
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    published_date = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title

    @property
    def num_copies_available(self):
        return self.physical_books.filter(borrowed_at__isnull=True).count()


class User(models.Model):
    name = models.TextField()

    def __str__(self) -> str:
        return self.name

class PhysicalBook(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='physical_books')
    borrowed_at = models.DateTimeField(null=True, blank=True)
    borrowed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self) -> str:
        return f"Physical copy of {self.book.title}"
