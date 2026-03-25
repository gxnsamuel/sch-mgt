from django_hosts import patterns, host
from django.conf import settings

host_patterns = patterns(
    '',
    host(r'www', settings.ROOT_URLCONF, name='www'),  # main site
    host(r'dash', 'dashboard.urls', name='dash'),  # dashboard subdomain
)