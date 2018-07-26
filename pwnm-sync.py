#!/usr/bin/python3
import datetime
import json
import requests
import notmuch
import sqlite3
import argparse
import os
import configparser
from requests_futures.sessions import FuturesSession

initial_argp = argparse.ArgumentParser(add_help=False)
initial_argp.add_argument("-c", "--config", dest='config_file', type=str,
                          help="Configuration file for pwnm-sync",
                          default=os.path.join(os.path.expanduser("~"),
                                               ".pwnm-sync.ini"))

args, remaining_argv = initial_argp.parse_known_args()
argp = argparse.ArgumentParser()

defaults = {
    "notmuch_database" : os.path.join(os.path.expanduser("~"),"Maildir","INBOX"),
    "syncdb" :          os.path.join(os.path.expanduser("~"),".pwnm-sync.db"),
    "patchwork_url" :    "https://patchwork.ozlabs.org",
    "sync" : "skiboot=skiboot@lists.ozlabs.org"
    }

if not os.path.isfile(args.config_file):
    print("Config file {} not found!".format(args.config_file))
    args.config_file = None

if args.config_file:
    config = configparser.SafeConfigParser()
    config.read([args.config_file])
    config_values = dict(config.items("Defaults"))
    defaults = {**defaults, **config_values}

argp.set_defaults(**defaults)
argp.add_argument("-m", "--notmuch-database", dest='notmuch_database', type=str,
                  help="The notmuch database to sync")
argp.add_argument("-d", "--syncdb", dest="syncdb", type=str,
                  help="The path to the sqlite3 database that pwnm-sync " +
                  "uses to keep track of the state of the local notmuch and " +
                  "remote patchwork databases.")
argp.add_argument("-t", "--patchwork-token", dest="patchwork_token", type=str,
                  help="Your Patchwork API token. Get it from /user/ on your " +
                  "patchwork instance.")
argp.add_argument("-p", "--patchwork-url", dest="patchwork_url", type=str,
                  help="The URL to your patchwork instance. Must support REST API.")
argp.add_argument("-s", "--sync", dest="sync", type=str,
                  help="Projects and lists to sync. " +
                  "In the format project1=list1@server1,project2=list2@server2")

args = argp.parse_args(remaining_argv)
print(args)


pw_token = args.patchwork_token
nmdb = args.notmuch_database
sync_db = args.syncdb

conn = sqlite3.connect(sync_db)

conn.execute('''CREATE TABLE IF NOT EXISTS pw_patch_status (
msgid text,
project text,
need_sync bool,
patchid int unique,
state text,
PRIMARY KEY(msgid,project))''')
conn.execute('''CREATE TABLE IF NOT EXISTS nm_patch_status (
msgid text,
project text,
need_sync bool,
state text,
PRIMARY KEY(msgid,project))''')
conn.commit()

all_my_tags = ['accepted', 'superseded', 'changes-requested',
               'rfc', 'rejected', 'new', 'under-review',
               'not-applicable', 'deferred', 'awaiting-upstream']


def get_oldest_nm_message(db, project_list):
    pw_list = 'to:{}'.format(project_list)
    qstr = pw_list
    #qstr = qstr + ' and not (tag:{}'.format(all_my_tags[0])
    #for t in all_my_tags[1:]:
    #    qstr = qstr + ' or tag:{}'.format(t)
    #qstr = qstr + ')'
    q = notmuch.Query(db, qstr)

    #q.exclude_tag('pwsync')
    q.set_sort(notmuch.Query.SORT.OLDEST_FIRST)
    #q.set_sort(notmuch.Query.SORT.NEWEST_FIRST)
    msgs = q.search_messages()
    since =  datetime.datetime.fromtimestamp(next(msgs).get_date())
    return since

def insert_nm_patch_status(conn,message_id,project_name,tag):
    conn.execute('''INSERT OR REPLACE INTO nm_patch_status
    (msgid, project, state, need_sync)
    VALUES (?,?,?,COALESCE((SELECT 1 FROM nm_patch_status WHERE msgid=? and project=? and state IS NOT ?),
                           (SELECT need_sync FROM nm_patch_status WHERE msgid=? and project=?),
                           0)
    )''',
                 (message_id, project_name, tag,
                  message_id, project_name, tag,
                  message_id, project_name))


def populate_nm_patch_status(db,conn,project_name,all_my_tags):
    for t in all_my_tags:
        qstr = 'tag:pw-{} and tag:pw-{}-{}'.format(project_name,project_name,t)
        q = notmuch.Query(db, qstr)
        msgs = q.search_messages()
        for m in msgs:
            insert_nm_patch_status(conn,m.get_message_id(),project_name,t)
        conn.commit()

def patchwork_login(session, url):
    patchwork_url = url + '/api'
    session.get(patchwork_url, stream=False).result()
    patchwork_url = patchwork_url + '/1.0'
    return patchwork_url


def get_projects(session, patchwork_url):
    url = patchwork_url + '/projects'

    projects = {}
    while True:
        r = session.get(url, params = {'per_page': 100}, stream=False).result()
        p = r.json()

        for project in p:
            #print(("{}\t{}".format(project['id'],project['link_name'])))
            projects[project['link_name']] = project['id']

        if not r.links.get('next'):
            break

        url = r.links['next']['url']

    return projects

def process_pw_patches(session, nmdb, project_name, r):
    nr_patches_processed = 0
    not_approved = {}
    done = False
    while not done:
        p = r.result().json()
        # We open the DB for each batch as to not hold the notmuch
        # database open blocking other writers for too long.
        db = notmuch.Database(nmdb, mode=notmuch.Database.MODE.READ_WRITE)
        # We initiate the async load of the next page now, as we go and make the
        # changes to our local DBs.
        if r.result().links.get('next'):
            r = session.get(r.result().links['next']['url'], stream=False)
        else:
            # This is the last page.
            done = True

        db.begin_atomic()
        for patch in p:
            nr_patches_processed = nr_patches_processed + 1
            conn.execute('''INSERT OR REPLACE INTO pw_patch_status
            (msgid,project,patchid,state,need_sync)
            VALUES (?,?,?,?,
            COALESCE((SELECT 1 FROM pw_patch_status WHERE msgid=? and project=? and state IS NOT ?),
                     (SELECT need_sync FROM pw_patch_status WHERE msgid=? and project=?),
                     0)
            )''',
                         (patch['msgid'][1:-1], project_name, patch['id'], patch['state'],
                          patch['msgid'][1:-1], project_name, patch['state'],
                          patch['msgid'][1:-1], project_name,
                         ))

            query_str = 'id:{}'.format(patch['msgid'][1:-1])
            q = notmuch.Query(db, query_str)
            msgs = q.search_messages()
            try:
                msg = next(msgs)
            except StopIteration:
                print("MESSAGE NOT FOUND: '{}' - skipping".format(query_str))
                # If we don't have the message, just continue.
                continue

            # If we need to update PW, skip setting the tags in nm
            c = conn.cursor()
            c.execute("SELECT state from nm_patch_status WHERE msgid=? AND project=? AND need_sync=1",
                      [patch['msgid'][1:-1],project_name])
            if c.fetchone():
                print("Going to sync {} to patchwork for {}".format(patch['msgid'],project_name))

            #msg.freeze()
            msg.add_tag('pw-{}'.format(project_name))
            for t in all_my_tags:
                msg.remove_tag('pw-{}-{}'.format(project_name,t))

            tag = patch['state']
            if tag in all_my_tags:
                msg.add_tag('pw-{}-{}'.format(project_name,tag))
            else:
                if not_approved.get(tag):
                    not_approved[tag] = not_approved[tag] + 1
                else:
                    not_approved[tag] = 1
                    #print("Not adding tag, as '{}'not in approved list".format(tag))
            #msg.thaw()
            insert_nm_patch_status(conn,patch['msgid'][1:-1],project_name,tag)
        db.end_atomic()
        conn.commit()
        db.close()

        print("Processed {} {} patches...".format(nr_patches_processed, project_name))

    print("Finished processing {} {} patches!".format(nr_patches_processed, project_name))
    print(not_approved)

s = FuturesSession()
s.headers.update({ 'Authorization': 'Token {}'.format(pw_token) })

patchwork_url = patchwork_login(s, args.patchwork_url)
projects = get_projects(s, patchwork_url)
#print(repr(projects))
def process_pw_patches_for_project(session, patchwork_url, project_name, project_id, oldest_msg):
    patches_url = patchwork_url + '/patches'

    r = session.get(patches_url, stream=False,
                    params={ 'per_page' : 500, 'since' : oldest_msg, 'project': project_id, })

    process_pw_patches(session, nmdb, project_name, r)

def update_patchwork(session, conn, project_name):
    cur = conn.cursor()
    for row in cur.execute('''
    SELECT
      pw_patch_status.patchid AS patchid,
      nm_patch_status.state as state,
      nm_patch_status.msgid as msgid
    FROM nm_patch_status, pw_patch_status
    WHERE pw_patch_status.msgid=nm_patch_status.msgid
      AND pw_patch_status.project=nm_patch_status.project
      AND nm_patch_status.project=? and nm_patch_status.need_sync=1''', [project_name]):
        print("Updating patch {} (id:{}) to {}".format(row[0],row[2],row[1]))
        session.patch(patchwork_url + '/patches/{}/'.format(row[0]),
                json={'state': row[1]}).result()
        r =  session.get(patchwork_url + '/patches/{}/'.format(row[0]))
        p = r.result().json()
        if row[1] == p['state']:
            conn.execute("UPDATE nm_patch_status SET need_sync=0 WHERE msgid=? AND project=?", [row[2],project_name])
        else:
            print("ERROR State didn't update for {} - are you maintainer of {}?".format(row[0],project_name))

for project in args.sync.split(","):
    project_name, project_list = project.split("=")

    print("Looking at project {} (id {})".format(project_name,projects[project_name]))
    db = notmuch.Database(nmdb)
    oldest_msg = get_oldest_nm_message(db, project_list)
    print("Going to look at things post {}".format(oldest_msg))
    populate_nm_patch_status(db,conn,project_name,all_my_tags)
    db.close() # close the read-only session

    # we now have a map of project names to IDs, so we can use that.
    process_pw_patches_for_project(s, patchwork_url, project_name, projects[project_name], oldest_msg)

    # We now know:
    # 1) What changed locally (nm_patch_status.need_sync=1)
    # 2) What changed remotely (pw_patch_status.need_sync=1)
    # 3) What has update conflicts (union of 1 and 2)
    # Current algorithm for conflicts is "take patchwork status"

    # This syncs the DB for anything with a update conflict
    #
    # We've already applied the PW status in the loop above.
    conn.execute("BEGIN")
    conn.execute('''UPDATE nm_patch_status
    SET need_sync=0
    WHERE
    project=? AND
    msgid in (SELECT msgid FROM pw_patch_status WHERE project=? and need_sync=1)''', [project_name,project_name])
    conn.commit()

    # We're now left with need_sync=1 on nm_patch_status for only
    # things we need to update in PW.
    update_patchwork(s, conn, project_name)

    # Things only updated in PW, ignore them (we've forced state sync above)
    conn.execute("UPDATE pw_patch_status set need_sync=0 WHERE project=? and need_sync=1", [project_name])

    conn.commit()

#print(json.dumps(r.json(), indent=2))
