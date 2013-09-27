"""

Mostly a copy of (django-registration/)registration/backends/default/urls.py and
registration/auth_urls.py, but using our own backends:

    * UsernameLessAuthenticationBackend for authentication
    * UsernameLessRegistrationBackend for registration

"""
from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template
from django.contrib.sites.models import Site
from django.contrib.auth import views as auth_views

from registration.views import activate
from registration.views import register

from forms import UsernameLessAuthenticationForm

auth_urls = patterns('',
                       url(r'^login/$',
                           auth_views.login,
                           {'template_name': 'registration/login.html',
                            'authentication_form': UsernameLessAuthenticationForm, },
                           name='auth_login'),
                       url(r'^logout/$',
                           auth_views.logout,
                           {'template_name': 'registration/logout.html'},
                           name='auth_logout'),
                       url(r'^password/change/$',
                           auth_views.password_change,
                           name='auth_password_change'),
                       url(r'^password/change/done/$',
                           auth_views.password_change_done,
                           name='auth_password_change_done'),
                       url(r'^password/reset/$',
                           auth_views.password_reset,
                           name='auth_password_reset'),
                       url(r'^password/reset/confirm/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$',
                           auth_views.password_reset_confirm,
                           name='auth_password_reset_confirm'),
                       url(r'^password/reset/complete/$',
                           auth_views.password_reset_complete,
                           name='auth_password_reset_complete'),
                       url(r'^password/reset/done/$',
                           auth_views.password_reset_done,
                           name='auth_password_reset_done'),
)

urlpatterns = patterns('',
                       url(r'^activate/complete/$',
                           direct_to_template,
                           {
                               'template': 'registration/activation_complete.html',
                               'extra_context': { 'site' : Site.objects.get_current() },
                           }, name='registration_activation_complete'),
                       # Activation keys get matched by \w+ instead of the more specific
                       # [a-fA-F0-9]{40} because a bad activation key should still get to the view;
                       # that way it can return a sensible "invalid key" message instead of a
                       # confusing 404.
                       url(r'^activate/(?P<activation_key>\w+)/$',
                           activate,
                           {'backend': 'usernameless.auth.UsernameLessRegistrationBackend'},
                           name='registration_activate'),
                       url(r'^register/$',
                           register,
                           {'backend': 'usernameless.auth.UsernameLessRegistrationBackend'},
                           name='registration_register'),
                       url(r'^register/complete/$',
                           direct_to_template,
                           {
                               'template': 'registration/registration_complete.html',
                               'extra_context': { 'site' : Site.objects.get_current() },
                           }, name='registration_complete'),
                       url(r'^register/closed/$',
                           direct_to_template,
                           {'template': 'registration/registration_closed.html'},
                           name='registration_disallowed'),
                       (r'', include(auth_urls)),
                       )
