#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2008  Étienne Loks  <etienne.loks_AT_peacefrogsDOTnet>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# See the file COPYING for details.

'''
Views management
'''

from random import choice as random_choice
import string
import time
from datetime import datetime

from django.utils.translation import gettext_lazy as _
from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect

from papillon.settings import LANGUAGES
from papillon.polls.models import Poll, PollUser, Choice, Voter, Vote, \
                                  Category, Comment

def getBaseResponse(request):
    """Manage basic fields for the template
    If not null the second argument returned is a redirection.
    """
    #Get the root url in order to redirect to the main page
    url = "/".join([request.META['HTTP_HOST'],
                    request.path.split('/')[1], ''])
    # setting the current language and available languages
    if 'language' in request.GET:
        if request.GET['language'] in [language[0] for language in LANGUAGES]:
            request.session['django_language'] = request.GET['language']
            return None, HttpResponseRedirect(request.path)
    languages = []
    for language_code, language_label in LANGUAGES:
        languages.append((language_code, language_label))
    return {'root_url':url, 'languages':languages}, None

def index(request):
    "Main page"
    response_dct, redirect = getBaseResponse(request)
    if redirect:
        return redirect
    response_dct['polls'] = Poll.objects.filter(public=True, category=None)
    response_dct['categories'] = Category.objects.all()
    error = ''
    if 'bad_poll' in request.GET:
        response_dct['error'] = _("The poll requested don't exist (anymore?)")
    return render_to_response('main.html', response_dct)

def category(request, category_id):
    "Page for a category"
    response_dct, redirect = getBaseResponse(request)
    if redirect:
        return redirect
    category = Category.objects.get(id=int(category_id))
    response_dct['category'] = category
    response_dct['polls'] = Poll.objects.filter(public=True, category=category)
    return render_to_response('category.html', response_dct)

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
        mandatory_fields = (('author_name', _("Author name")),
                            ('poll_name', _("Poll name")),
                            ('poll_desc', _("Poll description")),
                            ('poll_type', _("Poll type")),
                            )
        error = ""
        for key, label in mandatory_fields:
            if key not in request.POST or not request.POST[key]:
                # only the first error is reported
                if not error:
                    error = _("%s is a mandatory field") % label
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
        category = None
        if 'poll_category' in request.POST and request.POST['poll_category']:
            category = \
                     Category.objects.get(id=int(request.POST['poll_category']))
        public = False
        if 'poll_public' in request.POST and request.POST['poll_public']:
            value = False
            if request.POST['poll_public'] == '1':
                value = True
            public = value
        poll = Poll(name=request.POST['poll_name'],
description=request.POST['poll_desc'], author=author, base_url=base_url,
admin_url=admin_url, type=request.POST['poll_type'], category=category,
public=public)
        poll.save()
        url = response_dct['admin_url'] + '/%s/' % poll.admin_url
        return response_dct, HttpResponseRedirect(url)

    def getAndUpdateExistingPoll(request, response_dct, admin_url):
        "Get an existing poll"
        try:
            poll = Poll.objects.filter(admin_url=admin_url)[0]
        except IndexError:
            # if the poll don't exist redirect to the creation page
            url = response_dct['admin_url'] + '/0/'
            return response_dct, HttpResponseRedirect(url)
        # update the poll
        updated = None
        if 'poll_name' in request.POST and request.POST['poll_name']:
            updated = True
            poll.name = request.POST['poll_name']
        if 'poll_desc' in request.POST and request.POST['poll_desc']:
            updated = True
            poll.description = request.POST['poll_desc']
        if 'poll_open' in request.POST and request.POST['poll_open']:
            updated = True
            value = False
            if request.POST['poll_open'] == '1':
                value = True
            poll.open = value
        if 'poll_public' in request.POST and request.POST['poll_public']:
            updated = True
            value = False
            if request.POST['poll_public'] == '1':
                value = True
            poll.public = value
        if updated:
            poll.save()
        # base feed of the template
        new_dct = {'poll':poll,
          'choices':Choice.objects.filter(poll=poll).order_by('order'),
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
            limit = None
            if 'limit' in request.POST:
                try:
                    limit = int(request.POST['limit'])
                except ValueError:
                    # non numeric limit given : no limit set
                    pass
            choice = Choice(poll=poll, name=request.POST['new_choice'],
                            order=order, limit=limit)
            choice.save()
        # check if the order of a choice has to be changed
        for key in request.GET:
            try:
                if 'up_choice' in key:
                    choice = Choice.objects.get(id=int(request.GET[key]))
                    choice.changeOrder(-1)
                    # redirect in order to avoid a change with a refresh
                    url = response_dct['admin_url']
                    return response_dct, HttpResponseRedirect(url)
                if 'down_choice' in key:
                    choice = Choice.objects.get(id=int(request.GET[key]))
                    choice.changeOrder(1)
                    # redirect in order to avoid a change with a refresh
                    url = response_dct['admin_url']
                    return response_dct, HttpResponseRedirect(url)
            except (ValueError, Choice.DoesNotExist):
                pass
        # check if a choice has been choosen for deletion or for modification
        for key in request.POST:
            if key.startswith('delete_') and request.POST[key]:
                choice = Choice.objects.get(id=int(key[len('delete_'):]))
                Vote.objects.filter(choice=choice).delete()
                choice.delete()
            if key.startswith('modify_') and request.POST[key]:
                try:
                    choice = Choice.objects.get(id=int(key[len('modify_'):]))
                    choice.name = request.POST[key]
                    choice.save()
                except Choice.DoesNotExist:
                    # throw when want to modify a deleted choice
                    pass

            if key.startswith('limit_'):
                try:
                    choice = Choice.objects.get(id=int(key[len('limit_'):]))
                    if not request.POST[key]:
                        choice.limit = None
                        choice.save()
                    else:
                        try:
                            new_limit = int(request.POST[key])
                            sum = choice.getSum()
                            if new_limit < sum:
                                response_dct['error'] = _("You cannot lower \
%(name)s's limit to this number : there is currently %(sum)d votes for this \
choice.") % {'name':choice.name, 'sum':sum}
                            else:
                                choice.limit = new_limit
                                choice.save()
                        except ValueError:
                            response_dct['error'] = _("Non-numeric value for \
limit")
                except Choice.DoesNotExist:
                    # throw when want to modify a deleted choice
                    pass
        return response_dct, None

    response_dct, redirect = getBaseResponse(request)
    if redirect:
        return redirect
    response_dct['TYPES'] = Poll.TYPE
    response_dct['categories'] = Category.objects.all()
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
        response_dct, redirection = getAndUpdateExistingPoll(request,
                                               response_dct, admin_url)
    if redirection:
        return redirection
    return render_to_response('createOrEdit.html', response_dct)


def poll(request, poll_url):
    """Display a poll
    poll_url is given to identify the poll. If '_' is in the poll_url the second
    part of the url is the unix time given to highlight a particular vote
    modification
    """

    def modifyVote(request, choices):
        "Modify user's votes"
        try:
            voter = Voter.objects.filter(
                                  id=int(request.POST['voter']))[0]
        except (ValueError, IndexError):
            return
        # if no author_name is given deletion of associated votes and
        # author
        if not request.POST['author_name']:
            # verify if the author can be deleted
            delete_user = None
            if not voter.user.password:
                v = Voter.objects.filter(user=voter.user)
                if len(v) == 1 and v[0] == voter:
                    delete_user = voter.user
            for choice in choices:
                v = Vote.objects.filter(voter=voter, choice=choice)
                v.delete()
            voter.delete()
            if delete_user:
                delete_user.delete()
            return
        # update the name
        voter.user.name = request.POST['author_name']
        voter.user.save()
        # update the modification date
        voter.save()
        selected_choices = []
        # set the selected choices
        for key in request.POST:
            # modify a one choice poll
            if key == 'vote' and request.POST[key]:
                try:
                    id = int(request.POST[key])
                    vote = Vote.objects.filter(id=id)[0]
                    if vote.choice not in choices:
                        # bad vote id : the associated choice has
                        # probably been deleted
                        vote.delete()
                    else:
                        vote.value = 1
                        vote.save()
                        selected_choices.append(vote.choice)
                except (ValueError, IndexError):
                    # the vote don't exist anymore
                    pass
            # modify an existing vote
            if key.startswith('vote_') and request.POST[key]:
                try:
                    id = int(key.split('_')[1])
                    vote = Vote.objects.filter(id=id)[0]
                    if vote.choice not in choices:
                        # bad vote id : the associated choice has
                        # probably been deleted
                        vote.delete()
                    else:
                        # try if a specific value is specified in the form
                        # like in balanced poll
                        try:
                            value = int(request.POST[key])
                        except ValueError:
                            value = 1
                        vote.value = value
                        vote.save()
                        selected_choices.append(vote.choice)
                except (ValueError, IndexError):
                    # the vote don't exist anymore
                    pass
        # update non selected choices
        for choice in choices:
            if choice not in selected_choices:
                try:
                    v = Vote.objects.filter(voter=voter, choice=choice)[0]
                    v.value = 0
                except IndexError:
                    # the vote don't exist with this choice : probably
                    # a new choice
                    v = Vote(voter=voter, choice=choice, value=0)
                v.save()
    def newComment(request, poll):
        "Comment the poll"
        if 'comment_author' not in request.POST \
           or not request.POST['comment_author'] \
           or not request.POST['comment']:
            return
        c = Comment(poll=poll, author_name=request.POST['comment_author'],
                    text=request.POST['comment'])
        c.save()

    def newVote(request, choices):
        "Create new votes"
        if not request.POST['author_name']:
            return
        author = PollUser(name=request.POST['author_name'])
        author.save()
        voter = Voter(user=author, poll=poll)
        voter.save()
        selected_choices = []

        # set the selected choices
        for key in request.POST:
            # standard vote
            if key.startswith('choice_') and request.POST[key]:
                try:
                    id = int(key.split('_')[1])
                    choice = Choice.objects.filter(id=id)[0]
                    if choice not in choices:
                        raise ValueError
                    # try if a specific value is specified in the form
                    # like in balanced poll
                    try:
                        value = int(request.POST[key])
                    except ValueError:
                        value = 1
                    v = Vote(voter=voter, choice=choice, value=value)
                    v.save()
                    selected_choices.append(choice)
                except (ValueError, IndexError):
                    # bad choice id : the choice has probably been deleted
                    pass
            # one choice vote
            if key == 'choice' and request.POST[key]:
                try:
                    id = int(request.POST[key])
                    choice = Choice.objects.filter(id=id)[0]
                    if choice not in choices:
                        raise ValueError
                    v = Vote(voter=voter, choice=choice, value=1)
                    v.save()
                    selected_choices.append(choice)
                except (ValueError, IndexError):
                    # bad choice id : the choice has probably been deleted
                    pass
        # set non selected choices
        for choice in choices:
            if choice not in selected_choices:
                v = Vote(voter=voter, choice=choice, value=0)
                v.save()
        # results can now be displayed
        request.session['knowned_vote_' + poll.base_url] = 1
    response_dct, redirect = getBaseResponse(request)
    if redirect:
        return redirect
    highlight_vote_date = None
    if '_' in poll_url:
        url_spl = poll_url.split('_')
        if len(url_spl) == 2:
            poll_url, highlight_vote_date = url_spl
            try:
                highlight_vote_date = int(highlight_vote_date)
            except ValueError:
                highlight_vote_date = None
    try:
        poll = Poll.objects.filter(base_url=poll_url)[0]
    except IndexError:
        poll = None
    choices = list(Choice.objects.filter(poll=poll))
    # if the poll don't exist or if it has no choices the user is
    # redirected to the main page
    if not choices or not poll:
        url = "/".join(request.path.split('/')[:-3])
        url += "/?bad_poll=1"
        return HttpResponseRedirect(url)

    # a vote is submitted
    if 'author_name' in request.POST and poll.open:
        if 'voter' in request.POST:
            # modification of an old vote
            modifyVote(request, choices)
        else:
            newVote(request, choices)
        # update the modification date of the poll
        poll.save()
    if 'comment' in request.POST and poll.open:
        # comment posted
        newComment(request, poll)

    # 'voter' is in request.GET when the edit button is pushed
    if 'voter' in request.GET and poll.open:
        try:
            response_dct['current_voter_id'] = int(request.GET['voter'])
        except ValueError:
            pass

    response_dct.update({'poll':poll,
                         'VOTE':Vote.VOTE,})
    response_dct['base_url'] = "/".join(request.path.split('/')[:-2]) \
                               + '/%s/' % poll.base_url

    # get voters and sum for each choice for this poll
    voters = Voter.objects.filter(poll=poll)
    choice_ids = [choice.id for choice in choices]
    for voter in voters:
        # highlight a voter
        if time.mktime(voter.modification_date.timetuple()) \
                                                         == highlight_vote_date:
            voter.highlight = True
        voter.votes = voter.getVotes(choice_ids)
        # initialize undefined vote
        choice_vote_ids = [vote.choice.id for vote in voter.votes]
        for choice in choices:
            if choice.id not in choice_vote_ids:
                vote = Vote(voter=voter, choice=choice, value=None)
                vote.save()
                idx = choices.index(choice)
                voter.votes.insert(idx, vote)
    sums = [choice.getSum() for choice in choices]
    vote_max = max(sums)
    c_idx = 0
    while c_idx < len(choices):
        try:
            c_idx = sums.index(vote_max, c_idx)
            choices[c_idx].highlight = True
            c_idx += 1
        except ValueError:
            c_idx = len(choices)
    # set non-available choices if the limit is reached for a choice
    response_dct['limit_set'] = None
    for choice in choices:
        if choice.limit:
           response_dct['limit_set'] = True
        if choice.limit and sums[choices.index(choice)] >= choice.limit:
            choice.available = False
        else:
            choice.available = True
        choice.save()
    response_dct['voters'] = voters
    response_dct['choices'] = choices
    response_dct['comments'] = Comment.objects.filter(poll=poll)
    # verify if vote's result has to be displayed
    response_dct['hide_vote'] = True
    if u'display_result' in request.GET:
        request.session['knowned_vote_' + poll.base_url] = 1
    if 'knowned_vote_' + poll.base_url in request.session:
        response_dct['hide_vote'] = False
    return render_to_response('vote.html', response_dct)
