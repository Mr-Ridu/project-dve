"""Public-site data models."""
from django.db import models


class NewsletterSubscriber(models.Model):
    """One newsletter sign-up from the site's "Get Our Latest News" pop-up.

    The email is unique so a repeat sign-up refreshes the stored name and
    area of interest instead of creating a duplicate row.
    """

    class Interest(models.TextChoices):
        PLANT = "Industrial Plant & Machinery", "Industrial Plant & Machinery"
        ENERGY = "Energy & Power", "Energy & Power"
        ROBOTIC = "Robotic & Automation", "Robotic & Automation"
        STEEL = "Steel & Metal", "Steel & Metal"
        PHARMA = "Pharma & Biotech", "Pharma & Biotech"

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    email = models.EmailField(unique=True)
    interest = models.CharField(max_length=64, choices=Interest.choices, blank=True)
    consent = models.BooleanField(default=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "newsletter subscriber"
        verbose_name_plural = "newsletter subscribers"

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email
