#!/usr/bin/env python

from subprocess import call, check_output
from requests_kerberos import HTTPKerberosAuth
import click
import json
import requests

# This is a long, multi-parameter URL, there isn't a lot we can do about that
# pylint: disable=line-too-long
BUGZILLA_QUERY_URL = 'https://bugzilla.redhat.com/buglist.cgi?bug_status=MODIFIED&classification=Red%20Hat&f1=component&f2=component&f3=component&f4=cf_verified&keywords=UpcomingRelease&keywords_type=nowords&known_name=All%203.x%20MODIFIED%20Bugs&list_id=8111122&o1=notequals&o2=notequals&o3=notequals&o4=notequals&product=OpenShift%20Container%20Platform&query_based_on=All%203.x%20MODIFIED%20Bugs&query_format=advanced&short_desc=%5C%5Bfork%5C%5D&short_desc_type=notregexp&{0}&v1=RFE&v2=Documentation&v3=Security&v4=FailedQA&version=3.0.0&version=3.1.0&version=3.1.1&version=3.2.0&version=3.2.1&version=3.3.0&version=3.3.1&version=3.4.0&version=3.4.1&version=3.5.0&version=3.5.1&version=3.6.0&version=3.6.1&version=3.7.0&version=3.7.1&version=3.8.0&version=3.8.1&version=3.9.0&version=3.9.1&version=3.10.0&version=3.10.1&version=3.11.0&version=3.11.1&version=unspecified'

ERRATA_URL = "https://errata.devel.redhat.com"

GET_BUILDS_URL = ERRATA_URL + '/api/v1/erratum/{}/builds'
ADD_BUG_URL = ERRATA_URL + '/api/v1/erratum/{}/add_bug'
BUG_REFRESH_URL = ERRATA_URL + '/api/v1/bug/refresh'

SEPARATOR = '----------\n'


@click.group()
@click.pass_context
@click.option("--advisory",
              help="ID for the advisory to operate on")
@click.option('--verbose', '-v', default=False, is_flag=True, help='Enables verbose mode.')
@click.help_option('--help', '-h')
def cli(ctx, advisory, verbose):
    ctx.obj = {}
    ctx.obj['advisory'] = advisory
    ctx.obj['verbose'] = verbose


@cli.command("sweep", help="Add new MODIFED bugs to the advisory")
@click.option("--target_release",
              multiple=True,
              help="Target release versions (e.g. 3.9.x)")
@click.pass_context
def sweep(ctx):
    target_releases = ctx.obj['target_release']

    new_bugs = ctx.invoke(find_bugs)

    for release in target_releases:
        ctx.invoke(add_flag, flag='aos-{0}'.format(release), bug_list=new_bugs)

    ctx.invoke(refresh_bugs, bug_list=new_bugs)
    ctx.invoke(add_bugs, bug_list=new_bugs)


@cli.command("add_bugs", help="Add a list of bugs to the specified advisory")
@click.pass_context
def add_bugs(ctx, bug_list):
    advisory = ctx.obj['advisory']
    for bug in bug_list:
        click.echo("Adding Bug #{0} to Advisory {1}".format(bug, advisory))
        payload = {'bug': bug}
        requests.post(ADD_BUG_URL.format(advisory),
                      auth=HTTPKerberosAuth(),
                      json=payload)


@cli.command("fetch_builds", help="Find a list of builds for the advisory")
@click.pass_context
def fetch_builds(ctx):
    advisory = ctx.obj['advisory']

    response = requests.get(GET_BUILDS_URL.format(advisory),
                            auth=HTTPKerberosAuth())

    data = json.loads(response.content)

    for release_stream in data:
        click.echo("{}".format(release_stream))
        click.echo(SEPARATOR)

        builds = sorted([build.keys()[0].encode('utf-8')
                         for build in data[release_stream]['builds']])
        click.echo('\n'.join(builds))

        click.echo()


@cli.command("find_bugs", help="Find a list of bugs for a specified target release")
@click.option("--target_release",
              multiple=True,
              help="Target release versions (e.g. 3.9.x)")
@click.pass_context
def find_bugs(ctx):
    target_releases = ctx.obj['target_release']

    click.echo(
        "Searching bugzilla for MODIFIED bugs for release {0}".format(target_releases))

    # Example output: "target_release=3.4.z&target_release=3.5.z&target_release=3.6.z"
    target_releases_str = ''
    for release in target_releases:
        target_releases_str += 'target_release={0}&'.format(release)

    query_url = BUGZILLA_QUERY_URL.format(target_releases_str)
    if(ctx.obj['verbose']):
        click.echo(query_url)
    new_bugs = check_output(
        ['bugzilla', 'query', '--ids', '--from-url="{0}"'.format(query_url)]).splitlines()

    return new_bugs


@cli.command("flag_bugs", help="Add the release flag to a list of bugs")
@click.option("--flag",
              help="Flag to add to each bug in the list. Ex: aos-3.9.x")
@click.pass_context
def add_flag(ctx, flag, bug_list):
    for bug in bug_list:
        click.echo("Flagging Bug #{0} with {1}".format(bug, flag))
        call(['bugzilla', 'modify', '--flag', '{0}+'.format(flag), bug])


@cli.command("refresh_bugs", help="Refresh a list of bugs in errata tool")
@click.pass_context
def refresh_bugs(ctx, bug_list):
    payload = repr(bug_list)
    requests.post(BUG_REFRESH_URL,
                  auth=HTTPKerberosAuth(), data=payload)


cli.add_command(fetch_builds)
cli.add_command(sweep)

if __name__ == '__main__':
    # This is expected behaviour for context passing with click library:
    # pylint: disable=unexpected-keyword-arg
    cli(obj={})
