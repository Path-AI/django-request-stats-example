from rest_framework import serializers
from library.models import Book


class BookSerializer(serializers.ModelSerializer):
    author_name = serializers.ReadOnlyField(source='author.name')
    num_copies_available = serializers.\
        ReadOnlyField()

    class Meta:
        model = Book
        fields = ['title', 'author', 'author_name', 'num_copies_available']
