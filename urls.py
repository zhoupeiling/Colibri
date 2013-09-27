from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

from django.conf import settings
from registration.backends.default.urls import *


urlpatterns = patterns('',
    (r'^accounts/', include('main.urls')),
    (r'^admin/', include(admin.site.urls)),
)

urlpatterns += patterns('main.views',
    url(r'^about$', 'onlytemplate', {'template_name' : 'about.html'}, "about" ),
    url(r'^myaccount/$', 'myaccount'),
    url(r'^list/(.*)/archives/(\d+)/(\d+)/(.*)$', 'list_archives_date'),
    url(r'^list/(.*)/archives/(\d+)/$', 'list_archives_year'),
    url(r'^list/(.*)/archives/$', 'list_archives'),
    url(r'^list/(.*)/subscribers/$', 'list_subscribers'),
    url(r'^list/(.*)/subscribe/$', 'list_subscribe'),
    url(r'^list/(.*)/unsubscribe/$', 'list_unsubscribe'),
    url(r'^list/(.*)/manage/$', 'list_manage'),
    url(r'^list/(.*)/$', 'display_list_info'),
    url(r'^topic/(.*)/$', 'display_topic_info'),
    url(r'^$', 'main' ),
)

urlpatterns += patterns('main.views',
    url(r'^secondary_email/(\d+)/remove/$', 'remove_secondary_email'),
    url(r'^secondary_email/(\d+)/send_confirmation/$', 'confirm_secondary_email'),
    url(r'^secondary_email/(\d+)/switch/$', 'switch_secondary_email'),
    url(r'^secondary_email/activate/(?P<activation_key>\w+)/$', 'activate_secondary_email'),
)

if settings.DEBUG:
    import os.path
    urlpatterns += patterns('',
        url(r'^media/(?P<path>.*)$', 'django.views.static.serve', { 'document_root': settings.MEDIA_ROOT, }),
        url(r'^favicon.ico$', 'django.views.static.serve', { 'path': 'favicon.ico', 'document_root': os.path.join(settings.SITE_ROOT, 'static'), }),
        url(r'^robots.txt$', 'django.views.static.serve', { 'path': 'robots.txt', 'document_root': os.path.join(settings.SITE_ROOT, 'static'), }),
    )
