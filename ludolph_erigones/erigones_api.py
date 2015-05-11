"""
This file is part of Ludolph: Erigones SDDC API plugin
Copyright (C) 2015 Erigones, s. r. o.

See the LICENSE file for copying permission.
"""
import json
import time
import logging

from ludolph_erigones import __version__
from ludolph.command import CommandError, command
from ludolph.message import red, green, blue
from ludolph.plugins.plugin import LudolphPlugin

from erigones_sddc_api.client import Client
from erigones_sddc_api.exceptions import ESAPIError

logger = logging.getLogger(__name__)


class ErigonesApi(LudolphPlugin):
    """
    Erigones SDDC API commands. EXPERIMENTAL.

    https://my.erigones.com/docs/api/
    """
    __version__ = __version__
    _actions = {
        'post': 'POST',
        'create': 'POST',
        'put': 'PUT',
        'set': 'PUT',
        'delete': 'DELETE',
        'get': 'GET',
    }
    persistent_attrs = ('_user_auth',)

    def __init__(self, *args, **kwargs):
        """Read Ludolph plugin configuration [ludolph_erigones.erigones_api]"""
        super(ErigonesApi, self).__init__(*args, **kwargs)
        config = self.config
        self._id = 0
        self._user_es = {}
        self._user_auth = {}

        try:
            self._api_url = config['api_url'].rstrip('/')
        except KeyError:
            raise RuntimeError('api_url is not set in erigones_api plugin configuration')

    def _get_user_es(self, user, username_or_api_key, password):
        """Create :class:`erigones_sddc_api.Client` instance and perform Erigones SDDC API login"""
        err = ''

        if password:
            logger.debug('Signing in to Erigones SDDC API using user "%s" credentials', user)
            es = Client(api_url=self._api_url)

            try:
                es.login(username_or_api_key, password).content
            except Exception as exc:
                err = str(exc)
        else:
            logger.debug('Using user "%s" api_key - skipping Erigones SDDC API login', user)
            es = Client(api_url=self._api_url, api_key=username_or_api_key)

        if es.is_authenticated():
            logger.info('User "%s" login successful at %s', user, es)
        else:
            logger.error('User "%s" login problem at %s: "%s"', user, es, err)

        return es

    def _es_request(self, msg, method, resource, _after_relogin=False, **params):
        """Wrapper for getting Erigones SDDC API response with cached content and checking Erigones SDDC API errors"""
        user = self.xmpp.get_jid(msg)

        if user not in self._user_auth:
            logger.error('Erigones SDDC API is not available for user "%s"', user)
            raise CommandError('Erigones SDDC API is not available - use __es-login__ '
                               'to enable API access for your account (%s)' % user)

        try:
            es = self._user_es[user]
        except KeyError:
            es = self._user_es[user] = self._get_user_es(user, *self._user_auth[user])
            _after_relogin = True

        self._id += 1
        start_time = time.time()
        logger.info('[%s-%05d] User "%s" is calling Erigones SDDC API function: "%s %s"',
                    start_time, self._id, user, method, resource)
        response = es.request(method, resource, **params)

        if response.stream:
            self.xmpp.msg_reply(msg, 'Waiting for pending task %s ...' % blue(response.task_id), preserve_msg=True)

        try:
            response.content
        except ESAPIError as exc:
            if (exc.status_code == 403 and exc.detail == 'Authentication credentials were not provided.'
                    and self._user_auth[user][1] and not _after_relogin):
                logger.warning('Performing user "%s" re-login to Erigones SDDC API at %s', user, es)

                if es.login(*self._user_auth[user]).ok:
                    return self._es_request(msg, method, resource, _after_relogin=True, **params)

            if isinstance(exc.detail, (dict, list)):  # Create a bit nicer output
                try:
                    err = json.dumps(exc.detail, indent=4)
                except ValueError:
                    err = str(exc.detail)
            else:
                err = str(exc.detail)

            raise CommandError('%s %s: %s' % (exc.__class__.__name__, exc.status_code, err))
        finally:
            logger.info('[%s-%05d] Erigones SDDC API function "%s %s" called by user "%s" finished in %g seconds',
                        start_time, self._id, method, resource, user, (time.time() - start_time))

        return response

    @staticmethod
    def _parse_es_parameters(parameters):
        """The es command parameters parser"""
        params = {}
        key = None
        val_next = False

        for i in parameters:
            if i and i.startswith('-'):
                _key = i[1:]

                if _key and _key[0].isalnum():
                    key = _key
                    params[key] = True
                    val_next = True
                    continue

            if val_next and key:
                _i = str(i).lower()

                if _i == 'false':
                    params[key] = False
                elif _i == 'true':
                    params[key] = True
                elif _i == 'null':
                    params[key] = None
                elif i.startswith('json::'):
                    i = i[6:]
                    try:
                        i = json.loads(i)
                    except ValueError as e:
                        raise CommandError('Invalid json parameter %s (%s)' % (key, e))
                    else:
                        params[key] = i
                else:
                    params[key] = i

        return params

    @command
    def es_login(self, msg, username_or_api_key, password=None):
        """
        Sign in to Erigones SDDC API and save your custom api_key or username/password.

        Usage: es-login <api_key>
        Usage: es-login <username> <password>
        """
        user = self.xmpp.get_jid(msg)
        es = self._get_user_es(user, username_or_api_key, password)

        if es and es.get('/dc').ok:
            self._user_es[user] = es
            self._user_auth[user] = (username_or_api_key, password)
            self._db_save()
            return 'Successfully signed in to Erigones SDDC API (%s) and saved your (%s) credentials' % (self._api_url,
                                                                                                         user)
        else:
            raise CommandError('User **%s** authentication against Erigones SDDC API (%s) failed' % (user,
                                                                                                     self._api_url))

    @command
    def es_logout(self, msg):
        """
        Sign out of Erigones SDDC API and delete your credentials.

        Usage: es-logout
        """
        user = self.xmpp.get_jid(msg)
        es = self._user_es.pop(user, None)
        auth = self._user_auth.pop(user, None)

        if auth:
            logger.debug('Signing user "%s" out of Erigones SDDC API', user)
            self._db_save()

            if es and auth[1]:  # username/password authentication
                try:
                    es.logout().content
                except Exception as exc:
                    logger.warn('User "%s" logout problem at %s: "%s"', user, es, exc)
                else:
                    logger.info('User "%s" logout successful at %s', user, es)
            else:
                logger.info('User "%s" is using api_key or was never logged in - skipping logout at %s', user, es)

            return 'Successfully signed out of to Erigones SDDC API (%s) and removed your (%s) credentials' % (
                self._api_url, user)

        raise CommandError('User **%s** logout from Erigones SDDC API (%s) failed: user was never logged in' % (
            user, self._api_url))

    @command(admin_required=True)
    def es(self, msg, action, resource, *parameters):
        """
        es - Swiss Army Knife for Erigones SDDC API (EXPERIMENTAL)

        Usage: es action </resource> [parameters]

          action:\t{get|create|set|delete|options}
          resource:\t/some/resource/in/api
          parameters:\t-foo baz -bar qux ...
        """
        try:
            method = self._actions[action.lower()]
        except (KeyError, AttributeError):
            raise CommandError('Invalid action or method: **%s**' % action)

        if not resource.startswith('/'):
            raise CommandError('Invalid resource: **%s**' % resource)

        res = self._es_request(msg, method, resource, **self._parse_es_parameters(parameters))

        out = {
            'action': action,
            'resource': resource,
            'dc': res.dc,
            'task_id': res.task_id,
            '**status**': res.status_code,
            '**result**': res.content.result
        }

        return json.dumps(out, indent=4)

    @command(admin_required=True)
    def vm(self, msg, dc=None):
        """
        Show a list of all servers.

        Usage: vm [dc]
        """
        res = self._es_request(msg, 'GET', '/vm', dc=dc, full=True).content
        out = []

        def colorify(status):
            if status == 'running':
                color = green
            elif status == 'stopped' or vm['status'] == 'stopping':
                color = red
            elif status == 'pending':
                color = blue
            else:
                return status

            return color(status)

        for vm in res.result:
            out.append('**%s** (%s)\t%s' % (vm['hostname'], vm['alias'], colorify(vm['status'])))

        out.append('\n**%d** servers are shown in __%s__ datacenter.' % (len(res.result), res.dc))

        return '\n'.join(out)
