from pymongo import Connection
from remix.db import Contests, Contest, DataError
import datetime
import pymongo
import types

import pytest

def test_basics(contests):

    c = Contest(title="Contest Title", description="desc", slug="foo",
        source_id="8360")
    contest = contests.put(c)

    # try to retrieve the record again
    c2 = contests.get(contest['_id'])
    assert c2['title']=="Contest Title"
    assert c2['description']=="desc"
    assert isinstance(c2['_created'], datetime.datetime)
    assert isinstance(c2['_updated'], datetime.datetime)


def test_missing_field(contests):

    c = Contest(description="desc")
    pytest.raises(DataError, contests.put, c)
    try:
        contest = contests.put(c)
    except DataError, e:
        assert "title" in e.errors.keys()
        assert e.errors['title'].code == "required"
        assert e.results['description']=="desc"

def test_update_date(contests):
    c = Contest(title="test title", description="desc", slug="foo",
        source_id="8360")
    contest = contests.put(c)
    cid = contest['id']

    # retrieve it again and remember update time
    contest = contests[cid]
    upd = contest['_updated']

    contest.update({'title' : 'Neu'})
    contests.put(contest)

    contest = contests[cid]
    assert upd <= contest['_updated']



def test_created_date(contests):
    c = Contest(title="test title", description="desc", slug="foo",
        source_id="8360")
    contest = contests.put(c)
    cid = contest['id']

    # retrieve it again and remember update time
    contest = contests[cid]
    crd = contest['_created']

    contest.update({'title' : 'Neu'})
    contests.put(contest)

    contest = contests[cid]
    assert crd == contest['_created']



def test_update(contests):
    c = Contest(title="test title", description="desc", slug="foo",
        source_id="8360")
    contest = contests.put(c)
    cid = contest['id']

    # retrieve it again and remember update time
    contest = contests[cid]
    contest['title'] = "super"
    contests.put(contest)

    contest = contests[cid]
    assert contest['title'] == "super"
    assert contest['description'] == "desc"


def test_ids(contests):
    c = Contest(title="test title", description="desc", slug="foo",
        source_id="8360")
    contest = contests.put(c)

    assert type(contest['id']) == types.UnicodeType
    assert isinstance(contest['_id'], pymongo.objectid.ObjectId)


