#
# -*- coding: utf-8
#

#    Copyright (C) 2011 Thomas Capricelli <capricelli@sylphide-consulting.com>

from random import choice
from django.contrib.auth.models import User
from registration.backends.default.views import RegistrationView
from django.contrib.auth.backends import ModelBackend
from forms import UsernameLessRegistrationForm

chars_all='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
def random_string(length=10, allowed_chars=chars_all):
    return ''.join([choice(allowed_chars) for i in range(length)])

#
# Authentication
#
class UsernameLessAuthenticationBackend(ModelBackend):
    """
    tweak auth User-based authentication backend NOT to use username

    Use it by adding this to settings.py:
    AUTHENTICATION_BACKENDS = (
        usernameless.auth.UsernameLessAuthenticationBackend',
    )
    """
    def authenticate(self, email, password):
        try: 
            user = User.objects.get(email=email)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None

#
# Registration
#
class UsernameLessRegistrationBackend(RegistrationView):
    """
    Tweak django-registration DefaultBackend to NOT use username, by
    providing a random one.
    """
    def register(self, request, **kwargs):
        while True:
            username = random_string(8)  # 62^8 ~= 2E14
            if not User.objects.filter(username__iexact=username).exists(): break
        kwargs['username'] = username
        return RegistrationView.register(self, request, **kwargs)
    def get_form_class(self, request):
        return UsernameLessRegistrationForm
