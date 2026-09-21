"""Fail-closed subscription checks shared by CLI setup and reading engines."""
import json

from .modell import Motorsvar, Stotte


def subscription_confirmed(name, returncode, stdout, stderr=''):
    if returncode != 0:
        return False
    if name == 'claude':
        try:
            status = json.loads(stdout)
        except (ValueError, TypeError):
            return False
        return (isinstance(status, dict) and status.get('loggedIn') is True
                and status.get('authMethod') == 'claude.ai' and status.get('apiProvider') == 'firstParty')
    if name == 'codex':
        return 'Logged in using ChatGPT' in [line.strip() for line in (stdout + '\n' + stderr).splitlines()]
    return False


def auth_gate(name, verified):
    return {'status': 'verified' if verified else 'blocked',
            'scope': 'preflight_only',
            'code': None if verified else 'CLI_AUTH_REQUIRED',
            'reader': name + '_cli', 'automatic_fallback_allowed': False,
            'recovery_command': f'reader_setup.cmd {name} --login'}


def blocked_support(name):
    message = (f'CLI_AUTH_REQUIRED: Subscription sign-in for {name} could not be confirmed. '
               'Document analysis is blocked. Do not substitute host analysis, subagents, another reader, '
               'API calls or simulated results. You may prepare criteria and the plan, but produce no classifications. '
               f'Ask the user to run reader_setup.cmd {name} --login in a terminal, then check show_setup again. '
               'Resume only after sign-in is verified and the user asks to continue.')
    return Stotte(False, [message], {'auth_gate': auth_gate(name, False)})


def blocked_reply(support):
    return Motorsvar('', None, feil='; '.join(support.meldinger),
                     motorinfo={**support.egenskaper, 'stopp_ko': True})
