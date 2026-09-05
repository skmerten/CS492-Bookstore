from django.db import models

# Book model. Kind of straigh forward. Just data about books and inventory counts
# A few max character lengths
class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=200, blank=True)
    isbn = models.CharField(max_length=20, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    quantity = models.IntegerField(default=0)
    shelf_location = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.title