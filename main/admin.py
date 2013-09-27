#
# -*- coding: utf-8
#

#    Copyright (C) 2008-2011 Thomas Capricelli <orzel@freehackers.org>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.


from django.contrib import admin
from main.models import *

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('__unicode__', 'bounces_count', 'updated')
    list_filter = ('bounces_count', )
admin.site.register(Profile, ProfileAdmin)

class BounceAdmin(admin.ModelAdmin):
    list_display = ('profile', 'received', 'filename', 'status')
    search_fields = ('profile', 'filename')
    list_filter = ('datetime', 'received', 'status',)
    readonly_fields = ( 'filename', 'datetime', 'received', 'status', 'profile')
admin.site.register(Bounce, BounceAdmin)

class OtherEmailKeyAdmin(admin.ModelAdmin):
    list_display = ('otheremail', 'created')
    search_fields = ('otheremail', 'activation_key')
admin.site.register(OtherEmailKey, OtherEmailKeyAdmin)

class OtherEmailAdmin(admin.ModelAdmin):
    list_display = ('profile', 'email')
    search_fields = ('email',)
admin.site.register(OtherEmail, OtherEmailAdmin)

class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')
admin.site.register(Topic, TopicAdmin)

class ListAdmin(admin.ModelAdmin):
    filter_horizontal = ('topic', )
    list_display = ('name', 'host', 'owner', 'state', 'public', 'who_can_subscribe')
    search_fields = ('name', 'host', 'subject')
    list_filter = ('state', 'public', 'who_can_subscribe',)
admin.site.register(List, ListAdmin)

class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('profile', 'list', 'updated', 'option', 'moderator')
    list_filter = ('option', 'moderator', 'list')
admin.site.register(Subscription, SubscriptionAdmin)
