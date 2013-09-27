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

# System
from os.path import abspath
from os import stat, listdir
from platform import python_version

# django
from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseRedirect, Http404, HttpResponseServerError
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.template import Context, loader, RequestContext
from django.core.mail import send_mail
from django.conf import settings
from django import get_version

# project
from main.models import *
from main.forms import EmailForm, ListForm

ARCHIVE_DIR=abspath(settings.ARCHIVE_DIR)

#
# helpers
#
def find_email(email, checkOthers=True):
    """
    This helper try to find the email given in argument either in the User
    table or in the OtherEmail table. It returns a Profile object if found,
    and None else.
    """
    # first look in User
    users = User.objects.filter(email=email)
    if users.count()>1:
        # TODO : should not happen
        pass
    if users.count()>0:
        return users[0].get_profile()
    # then in OtherEmail
    if not checkOthers:
        return None
    others = OtherEmail.objects.filter(email=email, confirmed=True)
    if others .count()>1:
        # TODO : should not happen
        pass
    if others.count()>0:
        return others[0].profile
    # nothing found
    return None

def create_profile(user):
    profile = Profile()
    profile.user = user
    profile.save()
    return profile

def do_subscribe(profile,list):
    # create Subscription object
    subscription = Subscription()
    subscription.profile = profile
    subscription.list = list
    subscription.option = 1  # normal
    subscription.save()
    # send the welcome email
    email = profile.user.email
    subject = "Welcome to the mailing list %s" % unicode(list)
    message = render_to_string('welcome_email.txt',
                               { 'list': list,
                                 'email' : email,
                                 'site': Site.objects.get_current() })
    send_mail(subject, message,  list.list_address_extended('owner'), [email])
    return subscription

#
# views
#
def onlytemplate(request, template_name):
    context_instance=RequestContext(request)
    context_instance['python_version'] =  python_version()
    context_instance['django_version'] = get_version()
    return render_to_response(template_name, {'user':request.user}, context_instance=context_instance)

def server_error(request, template_name='500.html'):
    t = loader.get_template(template_name)
    return HttpResponseServerError(t.render(Context({
        "STATIC_URL" : settings.STATIC_URL,
    })))

def main(request):
    lists = List.objects.filter(public=True)
    return render_to_response('mainpage.html', {'lists': lists, 'topics':Topic.objects.filter(list__public=True) }, context_instance=RequestContext(request))

def display_topic_info(request, name):
    topic = get_object_or_404(Topic, name=name)
    lists = List.objects.filter(public=True).filter(topic=topic)
    return render_to_response('topic_info.html', {'topic': topic, 'lists':lists}, context_instance=RequestContext(request))

def display_list_info(request, name):
    list = getListFromName(name)
    subscription = None
    profile = None
    if request.user.is_authenticated():
        profile = request.user.get_profile()
        subscription = profile.list_subscription(list)
    su = request.user.is_authenticated() and request.user.is_staff
    if not list.public and subscription == None and not su:
        raise Http404
    can_browse_subscribers = list.subscribers_list_visible or (subscription and subscription.moderator)
    form = EmailForm()
    return render_to_response('list_info.html', {
        'profile': profile,
        'list': list,
        'can_browse_archive': list.can_browse_archive(subscription!=None) or request.user.is_staff,
        'can_browse_subscribers': can_browse_subscribers or request.user.is_staff,
        'subscription': subscription,
        'form': form,
    }, context_instance=RequestContext(request))

@require_POST
@login_required
def list_unsubscribe(request, name):
    list = getListFromName(name)
    profile = request.user.get_profile()
    subscription = profile.list_subscription(list)
    if subscription==None:
        return render_to_response("error.html", { "message": "You are not subscribed to this list, how did you get there ?", "returnpage" : "/list/%s/"%unicode(list)}, context_instance=RequestContext(request))
    # owner can not unsubscribe
    if list.owner.user==request.user:
        raise Http404("The owner of a mailing list can not unsubscribe")
    # actually unsubscribe
    subscription.delete()
    # send the resignation email
    email = profile.user.email
    subject = "You just quit the mailing list %s" % unicode(list)
    message = render_to_string('bye_email.txt',
                               { 'list': list,
                                 'email' : email,
                                 'site': Site.objects.get_current() })
    send_mail(subject, message,  list.list_address_extended('owner'), [email])
    return render_to_response('unsubscribed.html', {'list': list, }, context_instance=RequestContext(request))

def list_subscribe(request, name):
    list = getListFromName(name)
    if request.method != 'POST':
        # should not happen
        return render_to_response("error.html", { "message": "Unknown page, how did you get there ?.", "returnpage" : "/list/%s/"%unicode(list)}, context_instance=RequestContext(request))
    if request.user.is_authenticated():
        profile = request.user.get_profile()
        subscription = profile.list_subscription(list)
        if subscription!=None:
            return render_to_response("error.html", { "message": "You are already subscribed to this list, how did you get there ?", "returnpage" : "/list/%s/"%unicode(list)}, context_instance=RequestContext(request))
        # ok, actually subscribe this user
        do_subscribe(profile,list)
        return render_to_response('subscribed.html', {'list': list, }, context_instance=RequestContext(request))

    # ok : the remaining case is a non-identified user, trying to subscribe
    form = EmailForm(request.POST)

    #check the form
    if not form.is_valid():
        can_browse_archive = list.can_browse_archive(False)
        return render_to_response('list_info.html', {'profile':None, 'list': list, 'can_browse_archive':can_browse_archive, 'subscription':None, 'form':form}, context_instance=RequestContext(request))
        
    # check the email is not already known
    email = form.cleaned_data['email']
    profile = find_email(email)
    if profile !=None:
        return render_to_response("error.html", { "errorname":"Warning!", "message":
        """There is already an account using this email.
        
        If this is you, please identify yourself to proceed, if not, please choose another email to subscribe.

        If you have forgotten your password, you can <a href="/accounts/password/reset/">ask to change it here</a>.
        """, "returnpage" : "/accounts/login?next=/list/%s/"%unicode(list)}, context_instance=RequestContext(request))

    # first we need to create a user/profile
    from registration.models import RegistrationProfile
    # use a random password for now on, to be sure nobody can connect
    # the activation page will set the password
    password = User.objects.make_random_password()
    # we have meaningless 'username' in colibri, we only use the 'email'
    # field for authentication
    username = User.objects.make_random_password(25)
    new_user = RegistrationProfile.objects.create_inactive_user(username=username, password=password, site=Site.objects.get_current() , email=email, send_email=False)
    profile  = create_profile(new_user)

    # send an email about the new account
    registration_profile= RegistrationProfile.objects.get(user=new_user)
    subject = "Confirmation for subscribing to , "
    message = render_to_string('subscribe_email.txt',
                               { 'activation_key': registration_profile.activation_key,
                                 'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS,
                                 'list': list,
                                 'email' : email,
                                 'password' : password,
                                 'site': Site.objects.get_current() })
    send_mail(subject, message,  list.list_address_extended('owner'), [email])

    # actual subscribing + email
    do_subscribe(profile,list)

    return render_to_response('subscribed_and_account_created.html', {'list': list, }, context_instance=RequestContext(request))

def getListFromName(name):
    """
    Try to find the list whose name is given as argument, raises
    a 404 if not found.
    """
    split = name.split('@')
    if len(split)!=2:
        raise Http404("This list does not exist.")
    return get_object_or_404(List, name=split[0], host=split[1])

def list_archives(request, name):
    list = getListFromName(name)
    #checks
    subscribed = request.user.is_authenticated() and request.user.get_profile().list_subscription(list)!=None
    if not ( list.can_browse_archive(subscribed) or request.user.is_staff ):
        raise Http404("not allowed to browse archives")

    # find archives
    archive_dir = ARCHIVE_DIR+"/%s/" % unicode(list)
    try:
        years = listdir(archive_dir)
        years.sort()
    except OSError:
        # does not exist..
        return render_to_response('archives.html', {'list': list,}, context_instance=RequestContext(request))

    archives = []
    for year in years:
        months = listdir(archive_dir+year)
        months.sort(key=lambda m: int(m))
        archives.append ((year, months))
    return render_to_response('archives.html', {'list': list, 'archives': archives}, context_instance=RequestContext(request))

def list_subscribers(request, name):
    list = getListFromName(name)
    #checks
    subscription = None
    if request.user.is_authenticated():
        subscription = request.user.get_profile().list_subscription(list)
    can_browse_subscribers = list.subscribers_list_visible or (subscription and subscription.moderator)
    if not (can_browse_subscribers or request.user.is_staff):
        raise Http404("Not allowed to browse subscribers list")
    subscribers = [sub.profile for sub in Subscription.objects.filter(list=list).filter(profile__user__is_active=True)]
    return render_to_response('subscribers.html', {'list': list, 'subscribers': subscribers}, context_instance=RequestContext(request))

def list_archives_year(request, name, year):
    list = getListFromName(name)
    #checks
    assert(len(year)==4)
    assert(year.isdigit())
    subscribed = request.user.is_authenticated() and request.user.get_profile().list_subscription(list)!=None
    if not ( list.can_browse_archive(subscribed) or request.user.is_staff ):
        raise Http404("not allowed to browse archives")

    # find archives
    archive_dir = ARCHIVE_DIR+"/%s/%s/" % (unicode(list), year)
    try:
        months = listdir(archive_dir)
        months.sort(key=lambda m: int(m))
    except OSError:
        # does not exist..
        return render_to_response('archives_year.html', {'list': list, 'text': "No archive yet for this mailing list..." }, context_instance=RequestContext(request))

    archives = {}
    for month in months:
        assert(month.isdigit())
        archives[month] = len(listdir(archive_dir+month+'/text/'))

    return render_to_response('archives_year.html', {
        'list': list,
        'year': year,
        'archives': archives 
    }, context_instance=RequestContext(request))

def list_archives_date(request, name, year, month, path):
    list = getListFromName(name)
    #checks
    subscribed = request.user.is_authenticated() and request.user.get_profile().list_subscription(list)!=None
    if not ( list.can_browse_archive(subscribed) or request.user.is_staff ):
        raise Http404("not allowed to browse archives")
    # security check
    if ".." in path:
        raise Http404("Internal error: list_archives_date :  .. in the path")

    # handle last argument
    archive_index = ARCHIVE_DIR+"/%s/%s/%s/html/" % (unicode(list), year, month)
    if path=='':
        path = u"threads.html"
    if not path.endswith(".html"):
        # this is something else : just serve it as-is
        from django.views.static import serve
        return serve(request, path, document_root=archive_index)

    # ok, so we have an html file to include
    archive_index += path
    try:
        stat(archive_index)
    except OSError:
        # does not exist..
        raise Http404("Internal error: list_archives_date: can't stat the achive_index")
    # display it
    return render_to_response('archives_date.html', {'list': list, 'date': "%s-%s"%(year,month), 'archive_index':archive_index}, context_instance=RequestContext(request))

@login_required
def myaccount(request):
    profile = request.user.get_profile()

    if request.method == 'POST':
        form = EmailForm(request.POST)
        #check the form
        if form.is_valid():
            email=form.cleaned_data['email']
            otherprofile = find_email(email)
            if otherprofile == profile:
                return render_to_response("error.html", { "message":
                """This email address is already linked to your account.
                """, "returnpage" : "/myaccount/"}, context_instance=RequestContext(request))
            if otherprofile !=None:
                return render_to_response("error.html", { "message":
                """There is already an account using this email. You can
                not add it to your secondary emails list.
                """, "returnpage" : "/myaccount/"}, context_instance=RequestContext(request))

            secondary = OtherEmail(profile=profile,email=email)
            secondary.save()
            try:
                secondary.send_confirmation_mail()
            except:
                # ignore SMTP error
                pass
            return HttpResponseRedirect(reverse('main.views.myaccount'))
    else:
        form = EmailForm()
    return render_to_response('myaccount.html', { 'form':form, 'secondary_emails': profile.secondary_emails.all(), 'moderator_on': profile.subscription_set.filter(moderator=True), 'mylists':profile.own_lists.all(), 'subscriptions': profile.subscription_set.all(), }, context_instance=RequestContext(request))

@login_required
def remove_secondary_email(request, email_id):
    secondary = get_object_or_404(OtherEmail, id=email_id)
    secondary.delete()
    return HttpResponseRedirect(reverse('main.views.myaccount'))

@login_required
def confirm_secondary_email(request, email_id):
    secondary = get_object_or_404(OtherEmail, id=email_id)
    secondary.send_confirmation_mail()
    return HttpResponseRedirect(reverse('main.views.myaccount'))

@login_required
def switch_secondary_email(request, email_id):
    secondary = get_object_or_404(OtherEmail, id=email_id)
    # check
    if not secondary.confirmed:
        raise Http404("Unconfirmed email, how did you get there ?")
    # actual switch
    request.user.email , secondary.email = secondary.email, request.user.email
    request.user.save()
    secondary.save()
    return HttpResponseRedirect(reverse('main.views.myaccount'))

def activate_secondary_email(request, activation_key):
    """
    Mostly a copy/paste from django-registration activate()
    """
    # first find the key
    activation_key = activation_key.lower() # Normalize before trying anything with it.
    key = get_object_or_404(OtherEmailKey, activation_key=activation_key)

    # if connected... check the user
    # TODO

    # actual activation
    other = key.otheremail
    other.confirmed = True
    other.save()

    # clean
    OtherEmailKey.objects.filter(otheremail=other).delete()

    # go to the myaccount page where otheremails are displayed
    return HttpResponseRedirect(reverse('main.views.myaccount'))

@login_required
def list_manage(request, name):
    list = getListFromName(name) # or 404
    profile = request.user.get_profile()

    # check we are the owner
    if list.owner!=profile and not request.user.is_staff:
        raise Http404

    if request.method == 'POST':
        form = ListForm(request.POST, instance=list)
        #check the form
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('main.views.list_manage', args=[unicode(list),]))
    else:
        form = ListForm(instance=list)
    return render_to_response('list_manage.html', { 'form':form, }, context_instance=RequestContext(request))
