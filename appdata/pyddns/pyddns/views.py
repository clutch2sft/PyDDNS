#encoding:utf-8
from django.contrib.auth import authenticate, login as djlogin, logout as djlogout
from django.contrib.auth.decorators import login_required
#from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, HttpResponseRedirect
#from django.utils import simplejson
from django.shortcuts import render
from django.template  import RequestContext
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Max, Count
from django.contrib.auth.models import User

import json
import base64
import requests

#from common.utils import getForwardedFor
#from servers.models import Activity_log
from common.models import Activity_log
from datetime import datetime, timedelta
from django.conf import settings
from pyddns.models import SubDomain
from django.db.models import Q
from common.utils import getForwardedFor
from django.contrib.auth.decorators import user_passes_test

import socket
import dns.resolver
import logging
logger = logging.getLogger('django')

@login_required
def main(request,id_user=None):
    logger.debug("LOGIN")
    admin=False
    see_user=False

    own_admin=False
    if settings.OWN_ADMIN=="1" and not id_user:
        own_admin=True

    if request.user.is_superuser:
        admin=True

    if id_user:
        user=User.objects.get(id=id_user)
        see_user=True
    else:
        user=request.user
        id_user=request.user.id

    name = user.first_name
    username = user.username
    actividad=Activity_log.objects.filter(user_affected=username,action="SYNC")

    my_subdomains=SubDomain.objects.filter(user=user).order_by('name')
    domain=settings.DNS_DOMAIN

    ip_x_forwarded=None
    if 'HTTP_X_FORWARDED_FOR' in request.META:
        ip_x_forwarded=request.META['HTTP_X_FORWARDED_FOR']


    paginator = Paginator(actividad, 10) # Show 25 contacts per page
    page = request.GET.get('page')
    try:
        list_activity = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        list_activity = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        list_activity = paginator.page(paginator.num_pages)

    return render(request,"dash.html",{    'name':name,
                                            'username':username,
                                            'list_activity':list_activity,
                                            'my_subdomains':my_subdomains,
                                            'ip_x_forwarded':ip_x_forwarded,
                                            'admin':admin,
                                            'see_user':see_user,
                                            'domain':domain,
                                            'id_user': id_user,
                                            'own_admin':own_admin })

@login_required
def manage(request):
    domains=my_subdomains=SubDomain.objects.filter(user=request.user).order_by('name')

    paginator = Paginator(domains, 10) # Show 25 contacts per page
    page = request.GET.get('page')
    try:
        list_domains = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        list_domains = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        list_domains = paginator.page(paginator.num_pages)

    return render(request,"manage.html",{ 'list_domains': list_domains})


@user_passes_test(lambda u: u.is_superuser,login_url='/common/permission_denied')
def users(request, buscar=None):
    #logger.debug buscar
    users=User.objects.all().order_by('username')

    if buscar:
        users=users.filter( Q(first_name__icontains=buscar) | Q(last_name__icontains=buscar) | Q(username__icontains=buscar) )
    else:
        buscar=""
    paginator = Paginator(users, 6) # Show 25 contacts per page
    page = request.GET.get('page')
    try:
        list_users = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        list_users = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        list_users = paginator.page(paginator.num_pages)
    return render(request,"users.html",{ 'list_users': list_users, "buscar":buscar})


@user_passes_test(lambda u: u.is_superuser,login_url='/common/permission_denied')
def domains(request, buscar=None):
    subdomains=SubDomain.objects.all().order_by('name')

    #logger.debug buscar
    if buscar:
        subdomains=subdomains.filter( name__icontains=buscar )
    else:
        buscar=""

    domain=settings.DNS_DOMAIN

    paginator = Paginator(subdomains, 6) # Show 25 contacts per page
    page = request.GET.get('page')
    try:
        list_subdomains = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        list_subdomains = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        list_subdomains = paginator.page(paginator.num_pages)
    return render(request,"subdomains.html",{ 'list_subdomains': list_subdomains, "buscar":buscar, 'domain':domain })


@user_passes_test(lambda u: u.is_superuser,login_url='/common/permission_denied')
def add_user(request,id_user=None):
    user=None
    if id_user:
        try:
            user=User.objects.get(id=id_user)
            #logger.debug user
        except OstUserEmail.DoesNotExist:
            pass
            #logger.debug "DoesNotExist"
    return render(request,"add_user.html",{'user':user})

def add_subdomain(request):
    logger.debug("Entering add_subdomain view")
    myjson = {
        'error': "",
        'success': False,
    }


    if "subdomain" in request.POST.keys():
        subdomain=request.POST['subdomain']
        id_user=request.POST['id_user']

        user=User.objects.get(id=id_user)
        try:
            subdomain=SubDomain.objects.get(name=subdomain)
            myjson['error']= "exist"
        except SubDomain.DoesNotExist:
            admin=False
            if request.user.is_superuser:
                admin=True
            user_login=request.user

            if admin or user_login==user:
                subdomain=SubDomain(
                                        user=user,
                                        name=subdomain
                                    )
                subdomain.save()
                myjson['success']= True
            else:
                myjson['error']= "Not permission"
    return HttpResponse(json.dumps(myjson))


@user_passes_test(lambda u: u.is_superuser,login_url='/common/permission_denied')
def set_user(request):
    myjson = {
        'error': "",
        'success': False,
    }
    #logger.debug request.POST
    if "username" in request.POST.keys():
        username=request.POST['username']
        name=request.POST['name']
        last_name=request.POST['last_name']
        email=request.POST['email']
        password=request.POST['password']
        is_admin=request.POST['is_admin']

        if is_admin=="1":
            is_admin=True
        else:
            is_admin=False


        try:
            user_exist= User.objects.get(username=username)
            myjson['error']= "username exist"
            return HttpResponse(json.dumps(myjson))
        except User.DoesNotExist:
            user = User.objects.create_user(username=username,
                                             email=email,
                                             password=password)
            if password:
                #user.password=password
                user.set_password(password)
            user.first_name=name
            user.last_name=last_name
            user.is_superuser=is_admin
            user.save()
            myjson['success']= True
        Activity_log(action='EDIT USER', xforward=getForwardedFor(request), user_affected=request.user, result="Edit User --> name: %s"%user).save()


    elif "id_user" in request.POST.keys():
        name=request.POST['name']
        last_name=request.POST['last_name']
        email=request.POST['email']
        password=request.POST['password']
        is_admin=request.POST['is_admin']
        user= User.objects.get(id=request.POST['id_user'])
        if is_admin=="1":
            is_admin=True
        else:
            is_admin=False
        user.first_name=name
        user.last_name=last_name
        user.is_superuser=is_admin
        user.email=email
        if password:
            #user.password=password
            #logger.debug password
            user.set_password(password)
        user.save()
        myjson['success']= True
        Activity_log(action='SET USER', xforward=getForwardedFor(request), user_affected=request.user, result="Add User --> name: %s"%user).save()
    else:
        myjson['error']= "No se pasaron los datos por post"

    return HttpResponse(json.dumps(myjson))



@user_passes_test(lambda u: u.is_superuser,login_url='/common/permission_denied')
def delet_user(request):
    myjson = {
        'error': "",
        'success': False,
    }
    if "id_user" in request.POST.keys():
        id_user=request.POST['id_user']
        user= User.objects.get(id=request.POST['id_user'])
        user.delete()
        myjson['success']= True
        Activity_log(action='DELET USER', xforward=getForwardedFor(request), user_affected=request.user, result="Delet User --> name: %s"%user).save()
    else:
        myjson['error']= "No se pasaron los datos por post"
    return HttpResponse(json.dumps(myjson))

@login_required
def delet_domain(request):
    myjson = {
        'error': "",
        'success': False,
    }

    if "id_domain" in request.POST.keys():
        id_domain=request.POST['id_domain']
        domain= SubDomain.objects.get(id=id_domain)
        domain_name=domain.name
        domain_user=domain.user

        if request.user.is_superuser or request.user==domain_user:
            domain.delete()
            myjson['success']= True
            Activity_log(action='DELET DOMAIN', xforward=getForwardedFor(request), user_affected=domain_user, result="Delet domain --> name: %s"%domain_name).save()
        else:
            myjson['error']= "permission"
    else:
        myjson['error']= "No se pasaron los datos por post"
    return HttpResponse(json.dumps(myjson))



def set_ip_web(request,domain,ip):
    logger.debug("Entering set_ip_web view")
    myjson = {
        'message': '',
        'success': False,
    }

    admin=False
    user=request.user
    if user.is_superuser:
        admin=True

    #logger.debug "Dominio"
    #logger.debug domain
    subdomain=domain.split(".")[0]
    subdomain_obj=SubDomain.objects.get(name=subdomain)
    try:
        check_valid_subdomain=SubDomain.objects.get(user=user,name=subdomain)
    except SubDomain.DoesNotExist:
        check_valid_subdomain=False

    if check_valid_subdomain or admin:

        agent=""
        ip_x_forwarded=""
        username = user.username
        if 'HTTP_X_FORWARDED_FOR' in request.META:
            ip_x_forwarded=request.META['HTTP_X_FORWARDED_FOR']

        if 'HTTP_USER_AGENT' in request.META:
            agent=request.META['HTTP_USER_AGENT']

        return_code, message = set_ip(request,domain,ip)
        if return_code== "good":
            myjson['success'] = True
        else:
            myjson['message'] = message

        #logger.debug return_code
        #if return_code != "nochg":

        register=False
        last_activity=Activity_log.objects.filter(user_affected=username).last()
        if last_activity:
            if last_activity.code != return_code or return_code == "good":
                register=True
        else:
            register=True

        if register:
            Activity_log(action='SYNC', agent=agent , ip=ip, code=return_code, xforward=ip_x_forwarded, user_affected=subdomain_obj.user.username, domain=domain, result="%s"%(message)).save()

    return HttpResponse(json.dumps(myjson))






def set_ip(request,domain,ip):

    logger.debug("Entering set_ip view")
    #FOR TEST - DIG
    # ----------------------
    resolver = dns.resolver.Resolver()
    resolver.nameservers=[socket.gethostbyname('ddns')]
    try:
        ip_dig = resolver.query(domain,"A")[0]
    except:
        ip_dig=None

    if str(ip_dig) != str(ip):
        message=""
        subdomain=domain.split(".")[0]
        #logger.debug 'http://%s:%s/update?secret=%s&domain=%s&addr=%s'%(settings.DNS_HOST,settings.DNS_API_PORT,settings.DNS_SHARED_SECRET,subdomain,ip)
        #r = requests.get('http://%s:%s/update?secret=%s&domain=%s&addr=%s'%(settings.DNS_HOST,settings.DNS_API_PORT,settings.DNS_SHARED_SECRET,subdomain,ip))
        # Prepare the URL template
        url_template = "http://%s:%s/update?secret=%s&domain=%s&addr=%s"

        # Populate the URL with actual values
        actual_url = url_template % (settings.DNS_HOST, settings.DNS_API_PORT, settings.DNS_SHARED_SECRET, subdomain, ip)

        # logger.debug the URL to the terminal
        logger.debug(f"Making request to URL: {actual_url}")

        # Make the request
        r = requests.get(actual_url)

        #logger.debug r.json()
        #logger.debug r.json()['Success']
        if r.json()['Success']:
            return_code = "good"
            message = "The updatewas successful and the hostname is now updated"
        else:
            return_code = "dnserr"
            message = "The APP not sinc bind"
        #logger.debug return_code
        return return_code, message
    else:
        return "nochg", "It already exists"



def updateip(request):
    logger.debug("Entering updateip view")
    return_code="unknown"
    username=""
    domain=""
    ip=""
    ip_x_forwarded=""
    hostname=""
    message=""
    agent=""

    # Check if request is GET
    if request.method == 'GET':
        logger.debug(f"GET request: hostname = {request.GET.get('hostname')}, myip = {request.GET.get('myip')}")
        if 'hostname' in request.GET:
            domain=request.GET['hostname']
        if 'myip' in request.GET:
            ip=request.GET['myip']

    # Check for X-Forwarded-For header
    if 'HTTP_X_FORWARDED_FOR' in request.META:
        ip_x_forwarded=request.META['HTTP_X_FORWARDED_FOR']
        logger.debug(f"ip_x_forwarded: {ip_x_forwarded}")

    # Check for User-Agent header
    if 'HTTP_USER_AGENT' in request.META:
        agent=request.META['HTTP_USER_AGENT']
        logger.debug(f"agent: {request.META['HTTP_USER_AGENT']}")

    verified_agent=False
    if settings.DNS_ALLOW_AGENT:
        list_agent_allow=settings.DNS_ALLOW_AGENT.split(",")
        if list_agent_allow:
            for a in list_agent_allow:
                if a in request.META['HTTP_USER_AGENT']:
                    verified_agent=True
    else:
        verified_agent=True

    logger.debug(f"verified_agent: {verified_agent}")

    # Count failed attempts from same IP in last 10 minutes
    cant_fails=Activity_log.objects.filter(action='SYNC', ip=ip, date__gt=(datetime.now()-timedelta(minutes=10)), result__startswith='False').count()

    # Check for abuse (too many failed attempts)
    if cant_fails < 10:
        # Check if User-Agent is verified
        if verified_agent:
            # Check for HTTP Authorization header
            if 'HTTP_AUTHORIZATION' in request.META:
                auth = request.META['HTTP_AUTHORIZATION'].split()
                # Check if auth header has exactly two parts
                if len(auth) == 2:
                    # Check for Basic Authentication
                    if auth[0].lower() == "basic":
                        username, passwd = base64.b64decode(auth[1]).decode("utf-8", "ignore").split(':')
                        user = authenticate(username=username, password=passwd)
                        # Check for successful authentication
                        if user is not None and user.is_active:
                            user_subdomains = SubDomain.objects.filter(user=user)
                            valid_domain = False
                            # Check for valid subdomain
                            for sub in user_subdomains:
                                if domain == "%s.%s" % (sub.name, settings.DNS_DOMAIN):
                                    valid_domain = True
                            # If valid subdomain, proceed to set IP
                            if valid_domain:
                                return_code, message = set_ip(request, domain, ip)
                            # If subdomain not valid, log as "nohost"
                            else:
                                return_code = "nohost"
                                message = "The hostname specified does not exist in this user account"
                        # If authentication failed, log as "badauth"
                        else:
                            return_code = "badauth"
                            message = "The username and password pair do not match a real user"
                    # Handle unknown authentication method
                    else:
                        return_code = "unknown"
                        message = "Incorrect authentication format"
                # Handle malformed authentication header
                else:
                    return_code = "unknown"
                    message = "Incorrect authentication format"
            # Handle missing HTTP Authorization header
            else:
                return_code = "unknown"
                message = "Missing header HTTP_AUTHORIZATION"
        # Handle unverified User-Agent
        else:
            return_code = "badagent"
            message = "Missing header HTTP_USER_AGENT"
    # Handle too many failed attempts (abuse)
    else:
        return_code = "abuse"
        message = "You have exceeded the maximum number of attempts"

    # Register activity log if conditions are met
    register=False
    last_activity=Activity_log.objects.filter(user_affected=username).last()
    if last_activity:
        if last_activity.code != return_code or return_code == "good":
            register=True
    else:
        register=True

    # Log the activity (this is where failed attempts get logged)
    if register:
        Activity_log(action='SYNC', agent=agent , ip=ip, code=return_code, xforward=ip_x_forwarded, user_affected=username, domain=domain, result="%s"%(message)).save()

    return HttpResponse(return_code)

