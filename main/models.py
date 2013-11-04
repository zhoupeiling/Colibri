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


from django.db import models
from django.contrib.auth.models import User
from settings import ARCHIVE_DIR, ACCOUNT_ACTIVATION_DAYS, DEFAULT_FROM_EMAIL
from django.db.models import signals

class Profile(models.Model):
    user = models.ForeignKey(User, unique=True)
    bounces_count = models.PositiveIntegerField(default=0)
    updated = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.user.email
    def list_subscription(self,list):
        subscriptions = Subscription.objects.filter(profile=self).filter(list=list)
        if subscriptions.count()>1:
            # oops, several times!! put some warning somewhere
            pass
        if subscriptions.count()>0:
            return subscriptions[0]
        else:
            return None

class Bounce(models.Model):
    profile = models.ForeignKey(Profile, related_name="bounces_list")
    datetime = models.DateTimeField(null=True) # date found in the mail (not done yet)
    received = models.DateTimeField(auto_now_add=True) # date when the bounce was received by colibri
    filename = models.CharField(max_length=500) #  relative to BOUNCED_DIR
    status = models.CharField(max_length=500)

class OtherEmailKey(models.Model):
    """
    Highly inspired from django-registration RegistrationProfile, but this
    one only handles 'User', and here we want either CharField or
    OtherEmail
    """
    ACTIVATED = u"ALREADY_ACTIVATED"
    otheremail = models.ForeignKey("OtherEmail")
    activation_key = models.CharField(max_length=40)
    created = models.DateTimeField(auto_now_add=True)
    def __unicode__(self):
        return u"key for %s" % self.otheremail
    def activation_key_expired(self):
        expiration_date = datetime.timedelta(days=ACCOUNT_ACTIVATION_DAYS)
        return self.activation_key == self.ACTIVATED or \
               (self.created + expiration_date <= datetime.datetime.now())
    activation_key_expired.boolean = True

class OtherEmail(models.Model):
    profile = models.ForeignKey(Profile, related_name="secondary_emails")
    email = models.EmailField()
    confirmed = models.BooleanField(default=False)
    def __unicode__(self):
        return u"other key for %s (%s)" % (self.profile.user, self.email)
    def send_confirmation_mail(self):
        # create key
        from django.utils.hashcompat import sha_constructor
        import random
        from django.contrib.sites.models import Site
        from django.template.loader import render_to_string
        from django.core.mail import send_mail

        salt = sha_constructor(str(random.random())).hexdigest()[:5]
        activation_key = sha_constructor(salt+self.email).hexdigest()
        key = OtherEmailKey.objects.create(otheremail=self, activation_key=activation_key)
        subject = "Confirmation for a secondary email on %s" % Site.objects.get_current().name
        message = render_to_string('secondary_confirmation.txt',
                { 'activation_key': activation_key,
                'expiration_days': ACCOUNT_ACTIVATION_DAYS,
                'site': Site.objects.get_current() })
        send_mail(subject, message, DEFAULT_FROM_EMAIL, [self.email])

class Topic(models.Model):
    name = models.CharField(max_length=40)
    description = models.TextField()
    def __unicode__(self):
        return self.name

LIST_STATE_PRODUCTION = 1
LIST_STATE_REQUESTED = 2
LIST_STATE_ONHOLD = 3
LIST_STATE_DISABLED = 4
LIST_STATE_CHOICES = (
    (LIST_STATE_PRODUCTION, u'Production'),
    (LIST_STATE_REQUESTED, u'Requested' ),
    (LIST_STATE_ONHOLD, u'On hold'),
    (LIST_STATE_DISABLED, u'Disabled')
)

LIST_SUBSCRIPTION_OPEN = 1
LIST_SUBSCRIPTION_ADMIN = 2
LIST_SUBSCRIPTION_CLOSED = 3
LIST_SUBSCRIPTION_CHOICES = (
    (LIST_SUBSCRIPTION_OPEN, u'Everybody can subscribe'),
    (LIST_SUBSCRIPTION_ADMIN, u'The admin must accept the request' ),
    (LIST_SUBSCRIPTION_CLOSED, u'No new subscription allowed'),
)

LIST_MODERATE_ACCEPT = 1
LIST_MODERATE_MODERATE = 2
LIST_MODERATE_DENY = 3
LIST_MODERATE_CHOICES = (
    (LIST_MODERATE_ACCEPT, u'Always accept'),
    (LIST_MODERATE_MODERATE, u'Moderate' ),
    (LIST_MODERATE_DENY, u'Always deny'),
)

LIST_ARCHIVE_EVERYBODY = 1
LIST_ARCHIVE_MEMBERS = 2
LIST_ARCHIVE_NOBODY = 3
LIST_ARCHIVE_CHOICES = (
    (LIST_ARCHIVE_EVERYBODY, u'Everybody can browse'),
    (LIST_ARCHIVE_MEMBERS, u'Only members can browse'),
    (LIST_ARCHIVE_NOBODY, u'Nobody can browse'),
)

class List(models.Model):
    name = models.CharField(max_length=40)
    host = models.CharField(max_length=40)

    # information about the list
    subject = models.CharField(max_length=40) # oneliner
    topic = models.ManyToManyField(Topic, blank=True)
    description = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    # who
    owner = models.ForeignKey(Profile, related_name="own_lists")

    # states
    state = models.IntegerField(choices=LIST_STATE_CHOICES, default=LIST_STATE_REQUESTED)
    public = models.BooleanField(default=True, help_text=u"Publicly visible")
    who_can_subscribe = models.IntegerField(choices=LIST_SUBSCRIPTION_CHOICES, default=LIST_SUBSCRIPTION_OPEN)

    # posting
    posting_from_subscriber = models.IntegerField(choices=LIST_MODERATE_CHOICES, default=LIST_MODERATE_ACCEPT)
    posting_from_external = models.IntegerField("Posting from non subscriber", choices=LIST_MODERATE_CHOICES, default=LIST_MODERATE_MODERATE)
    mail_with_attachement = models.IntegerField(choices=LIST_MODERATE_CHOICES, default=LIST_MODERATE_MODERATE)
    mail_as_bcc = models.IntegerField(choices=LIST_MODERATE_CHOICES, default=LIST_MODERATE_MODERATE)
    probably_spam = models.IntegerField(choices=LIST_MODERATE_CHOICES, default=LIST_MODERATE_MODERATE)

    # misc settings
    archive_browsing = models.IntegerField(choices=LIST_ARCHIVE_CHOICES, default=2)
    subscribers_list_visible = models.BooleanField(default=True, help_text=u"Can the subscribers browse the list of subscribers ?")
    include_author_in_reply_to = models.BooleanField(default=True, help_text=u"Should we include the original author in the reply-to header ? (The mailing list address is always included)")

    # customization
    subject_tag = models.CharField(max_length=20, blank=True, help_text=u"This will be added in the subject using brackets. You do NOT need to write the brackets yourself!")
    max_size = models.PositiveIntegerField(default=4*1024*1024)
    subscribe = models.TextField(blank=True)
    unsubscribe = models.TextField(blank=True)
    header = models.TextField(blank=True)
    trailer = models.TextField(blank=True)

    def __unicode__(self):
        return u"%s@%s" % (self.name, self.host)
    def list_id(self):
        """
        return the string suitable for 'List-Id' in mail header
        """
        return u"%s.%s" % (self.name, self.host)
    def list_address_extended(self, extension):
        """ Return a string in the form <name>-<extension>@<host>, where
        extension is given as first argument """
        return u"%s-%s@%s" % (self.name, extension, self.host)
    def can_browse_archive(self, subscribed):
        return self.archive_browsing==LIST_ARCHIVE_EVERYBODY or (self.archive_browsing==LIST_ARCHIVE_MEMBERS and subscribed)

SUBSCRIPTION_MAIL_OPTION_NORMAL = 1
SUBSCRIPTION_MAIL_OPTION_DIGEST = 2
SUBSCRIPTION_MAIL_OPTION_ONHOLD = 3
SUBSCRIPTION_MAIL_OPTION_CHOICES = (
    (SUBSCRIPTION_MAIL_OPTION_NORMAL, u'Normal'),
    (SUBSCRIPTION_MAIL_OPTION_DIGEST, u'Digest' ),
    (SUBSCRIPTION_MAIL_OPTION_ONHOLD, u'On Hold'),
)

class Subscription(models.Model):
    profile = models.ForeignKey(Profile)
    list = models.ForeignKey(List) #dangerous, 'list' is the name of a python class
    started = models.DateTimeField(auto_now_add=True) # date of subscription
    updated = models.DateTimeField(auto_now=True)
    option = models.IntegerField(choices=SUBSCRIPTION_MAIL_OPTION_CHOICES, default=SUBSCRIPTION_MAIL_OPTION_NORMAL)
    moderator = models.BooleanField(default=False)
    class Meta:
        unique_together = ('profile', 'list',)

def user_post_save_handler(sender, instance, created, signal, *args, **kwargs):
    if created:
        Profile.objects.create(user=instance)

signals.post_save.connect(user_post_save_handler, sender=User)
