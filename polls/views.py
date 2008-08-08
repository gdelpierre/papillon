#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2008  Étienne Loks  <etienne.loks_AT_peacefrogsDOTnet>
# This program can be distributed under the terms of the GNU GPL.
# See the file COPYING.

from random import choice as random_choice
import string
import time

from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect

from papillon.polls.models import Poll, PollUser, Choice, Vote

def getBaseResponse(request):
    "Get the root url in order to redirect to the main page"
    url = "/".join([request.META['HTTP_HOST'], 
                    request.path.split('/')[1], '']) 
    return {'root_url':url}

def index(request):
    "Main page"
    response_dct = getBaseResponse(request)
    error = ''
    if 'bad_poll' in request.GET:
        response_dct['error'] = "The poll requested don't exist (anymore?)"
    return render_to_response('main.html', response_dct)

def createOrEdit(request, admin_url):
    '''Creation or edition of a poll.
    admin_url is given to identify a particular poll
    admin_url is equal to 0 for a new poll
    response_dct is given to the template with some particular keys:
     - error is an error message
     - new is set to true if it is a new poll
     - admin_url is the url of the current page
    '''
    def genRandomURL():
        "Generation of a random url"
        chars = string.letters + string.digits
        url = ''    
        for i in xrange(6):
            url += random_choice(chars)
        url += str(int(time.time()))
        return url
    
    def submitNewPoll(request, response_dct):
        "A new poll is submited"
        # verify if all the mandatory_fields are set
        mandatory_fields = (('author_name', "Author name"),
                            ('poll_name', "Poll name"),
                            ('poll_desc', "Poll description"),
                            ('poll_type', "Poll type"),
                            )
        error = ""
        for key, label in mandatory_fields:
            if key not in request.POST or not request.POST[key]:
                # only the first error is reported
                if not error:
                    error = "%s is a mandatory field" % label
            else:
                response_dct[key] = request.POST[key]
        if error:
            response_dct['new'] = True
            response_dct['error'] = error
            response_dct['admin_url'] += '/0/'
            return response_dct, None
        author = PollUser(name=request.POST['author_name'])
        author.save()
        base_url = 'b' + genRandomURL()
        admin_url = 'a' + genRandomURL()
        poll = Poll(name=request.POST['poll_name'],
description=request.POST['poll_desc'], author=author, base_url=base_url,
admin_url=admin_url, status = 'D', type=request.POST['poll_type'])
        poll.save()
        url = response_dct['admin_url'] + '/%s/' % poll.admin_url
        return response_dct, HttpResponseRedirect(url)
    
    def getExistingPoll(request, response_dct, admin_url):
        "Get an existing poll"
        try:
            poll = Poll.objects.filter(admin_url=admin_url)[0]
        except IndexError:
            # if the poll don't exist redirect to the creation page
            url = response_dct['admin_url'] + '/0/'
            return response_dct, HttpResponseRedirect(url)
        # base feed of the template
        new_dct = {'author_name':poll.author.name,
          'poll_name':poll.name,
          'poll_desc':poll.description,
          'choices':Choice.objects.filter(poll=poll).order_by('order'),
          'poll_status':poll.status,
          'type_name':poll.getTypeLabel()}
        response_dct.update(new_dct)
        
        # urls
        base_path = request.META['HTTP_HOST'] + \
                    "/".join(request.path.split('/')[:-3])
        response_dct['base_url'] = poll.base_url
        response_dct['full_base_url'] = base_path + "/poll/" \
                                   + poll.base_url + "/"
        response_dct['admin_url'] += '/%s/' % poll.admin_url
        response_dct['full_admin_url'] = base_path + "/edit/" \
                                         + admin_url + "/"
        
        # if a new choice is submitted
        if 'new_choice' in request.POST and request.POST['new_choice']:
            try:
                order = Choice.objects.order_by('-order')[0].order
                order += 1
            except IndexError:
                order = 0
            choice = Choice(poll=poll, name=request.POST['new_choice'],
                            order=order) 
            choice.save()
        # check if a choice has been choosen for deletion 
        for key in request.POST:
            if key.startswith('delete_') and request.POST[key]:
                choice = Choice.objects.get(id=int(key[len('delete_'):]))
                Vote.objects.filter(choice=choice).delete()
                choice.delete()
        return response_dct, None
    
    response_dct = getBaseResponse(request)
    response_dct['TYPES'] = Poll.TYPE
    response_dct['admin_url'] = \
                         "/".join(request.path.split('/')[:-2])
    redirection = None
    if 'new' in request.POST:
        # new poll is submited
        response_dct, redirection = submitNewPoll(request, response_dct)
    elif admin_url == '0':
        # new empty poll
        response_dct['new'] = True
        response_dct['admin_url'] += '/0/'
    else:
        # existing poll
        response_dct, redirection = getExistingPoll(request, 
                                               response_dct, admin_url)
    if redirection:
        return redirection
    return render_to_response('createOrEdit.html', response_dct)


def poll(request, poll_url):
    "Display a poll"
    
    def modifyVote(request, choices):
        "Modify user's votes"
        try:
            author = PollUser.objects.filter(
                                  id=int(request.POST['voter']))[0]
        except (ValueError, IndexError):
            return
        # if no author_name is given deletion of associated votes and 
        # author
        if not request.POST['author_name']:
            for choice in choices:
                v = Vote.objects.filter(voter=author, choice=choice)
                v.delete()
            author.delete()
            return
        # update the name
        author.name = request.POST['author_name']
        author.save()
        selected_choices = []
        # set the selected choices
        for key in request.POST:
            if key.startswith('vote_') and request.POST[key]:
                try:
                    id = int(key.split('_')[1])
                    vote = Vote.objects.filter(id=id)[0]
                    if vote.choice not in choices:
                        # bad vote id : the associated choice has
                        # probably been deleted
                        vote.delete()
                    else:
                        vote.vote = 1
                        vote.save()
                        selected_choices.append(vote.choice)
                except (ValueError, IndexError):
                    # the vote don't exist with this choice
                    v = Vote(voter=author, choice=choice, value=1)
                    v.save()
            if key.startswith('choice_') and request.POST[key]:
                try:
                    id = int(key.split('_')[1])
                    choice = Choice.objects.filter(id=id)[0]
                    if choice not in choices:
                        raise ValueError
                    v = Vote(voter=author, choice=choice, value=1)
                    v.save()
                    selected_choices.append(choice)
                except (ValueError, IndexError):
                    # bad choice id : the choice has probably been deleted
                    pass
        # update non selected choices
        for choice in choices:
            if choice not in selected_choices:
                try:
                    v = Vote.objects.filter(voter=author, choice=choice)[0]
                    v.vote = 0
                except IndexError:
                    # the vote don't exist with this choice : probably
                    # a new choice
                    v = Vote(voter=author, choice=choice, value=0)
                v.save()

    def newVote(request, choices):
        "Create new votes"
        if not request.POST['author_name']:
            return
        author = PollUser(name=request.POST['author_name'])
        author.save()
        selected_choices = []
        
        # set the selected choices
        for key in request.POST:
            if key.startswith('choice_') and request.POST[key]:
                try:
                    id = int(key.split('_')[1])
                    choice = Choice.objects.filter(id=id)[0]
                    if choice not in choices:
                        raise ValueError
                    v = Vote(voter=author, choice=choice, value=1)
                    v.save()
                    selected_choices.append(choice)
                except (ValueError, IndexError):
                    # bad choice id : the choice has probably been deleted
                    pass
        # set non selected choices
        for choice in choices:
            if choice not in selected_choices:
                v = Vote(voter=author, choice=choice, value=0)
                v.save()

    response_dct = getBaseResponse(request)
    try:
        poll = Poll.objects.filter(base_url=poll_url)[0]
    except IndexError:
        poll = None
    choices = Choice.objects.filter(poll=poll).order_by('order')
    # if the poll don't exist or if it has no choices the user is
    # redirected to the main page
    if not choices or not poll:    
        url = "/".join(request.path.split('/')[:-3])
        url += "/?bad_poll=1"
        return HttpResponseRedirect(url)
    
    # a vote is submitted
    if 'author_name' in request.POST:
        if 'voter' in request.POST:
            # modification of an old vote
            modifyVote(request, choices)
        else:
            newVote(request, choices)
    
    # 'voter' is in request.GET when the edit button is pushed
    if 'voter' in request.GET:
        try:
            response_dct['current_voter_id'] = int(request.GET['voter'])
        except ValueError:
            pass
    
    response_dct.update({'choices':choices,
                         'poll_type_name':poll.getTypeLabel(),
                         'poll_name':poll.name,
                         'poll_desc':poll.description})
    response_dct['base_url'] = "/".join(request.path.split('/')[:-2]) \
                               + '/%s/' % poll.base_url
    
    # get voters and sum for each choice for this poll

    votes = [] # all votes for this poll
    votes = Vote.objects.extra(where=['choice_id IN (%s)' \
                   % ",".join([str(choice.id) for choice in choices])])
    
    voters = []
    choices_sum = [0 for choice in choices]
    choices_ids = [choice.id for choice in choices]
    for vote in votes:
        if vote.voter not in voters:
            # initialize a votes list for the current voter
            vote.voter.votes = [None for choice in choices]
            voters.append(vote.voter)
            voter = vote.voter
        else:
            # get the appropriate voter
            voter = voters[voters.index(vote.voter)]
        idx = choices_ids.index(vote.choice.id)
        # associate vote in the votes list of the voter
        voter.votes[idx] = vote
        choices_sum[idx] += vote.value
    # for undefined vote get the choice id
    # on the template the distinction between the choice and the voter
    # is made by the type of the "vote"
    for voter in voters:
        for vote in voter.votes:
            if not vote:
                idx = voter.votes.index(vote)
                voter.votes[idx] = choices[idx].id
    response_dct.update({'voters':voters,
                        'voter':voters,
                        'choices_sum':[str(sum) for sum in choices_sum]
                        })
    return render_to_response('vote.html', response_dct)
