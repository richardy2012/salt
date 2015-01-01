# -*- coding: utf-8 -*-
'''
Execute salt convenience routines
'''

# Import python libs
from __future__ import print_function
from __future__ import absolute_import
import logging

# Import salt libs
import salt.exceptions
import salt.loader
import salt.minion
import salt.utils.args
import salt.utils.event
from salt.client import mixins
from salt.output import display_output

log = logging.getLogger(__name__)


class RunnerClient(mixins.SyncClientMixin, mixins.AsyncClientMixin, object):
    '''
    The interface used by the :command:`salt-run` CLI tool on the Salt Master

    It executes :ref:`runner modules <all-salt.runners>` which run on the Salt
    Master.

    Importing and using ``RunnerClient`` must be done on the same machine as
    the Salt Master and it must be done using the same user that the Salt
    Master is running as.

    Salt's :conf_master:`external_auth` can be used to authenticate calls. The
    eauth user must be authorized to execute runner modules: (``@runner``).
    Only the :py:meth:`master_call` below supports eauth.
    '''
    client = 'runner'
    tag_prefix = 'run'

    def __init__(self, opts):
        super(RunnerClient, self).__init__(opts)
        self.functions = salt.loader.runner(opts)  # Must be self.functions for mixin to work correctly :-/
        self.returners = salt.loader.returners(opts, self.functions)
        self.outputters = salt.loader.outputters(opts)

    def _reformat_low(self, low):
        '''
        Format the low data for RunnerClient()'s master_call() function

        The master_call function here has a different function signature than
        on WheelClient. So extract all the eauth keys and the fun key and
        assume everything else is a kwarg to pass along to the runner function
        to be called.
        '''
        auth_creds = dict([(i, low.pop(i)) for i in [
                'username', 'password', 'eauth', 'token', 'client',
            ] if i in low])
        reformatted_low = {'fun': low.pop('fun')}
        reformatted_low.update(auth_creds)
        reformatted_low['kwarg'] = low
        return reformatted_low

    def cmd_async(self, low):
        '''
        Execute a runner function asynchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized to execute runner functions: (``@runner``).

        .. code-block:: python

            runner.eauth_async({
                'fun': 'jobs.list_jobs',
                'username': 'saltdev',
                'password': 'saltdev',
                'eauth': 'pam',
            })
        '''
        reformatted_low = self._reformat_low(low)

        return mixins.AsyncClientMixin.cmd_async(**reformatted_low)

    def cmd_sync(self, low, timeout=None):
        '''
        Execute a runner function synchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized to execute runner functions: (``@runner``).

        .. code-block:: python

            runner.eauth_sync({
                'fun': 'jobs.list_jobs',
                'username': 'saltdev',
                'password': 'saltdev',
                'eauth': 'pam',
            })
        '''
        reformatted_low = self._reformat_low(low)
        return mixins.SyncClientMixin.cmd_sync(**reformatted_low)


class Runner(RunnerClient):
    '''
    Execute the salt runner interface
    '''
    def print_docs(self):
        '''
        Print out the documentation!
        '''
        arg = self.opts.get('fun', None)
        docs = super(Runner, self).get_docs(arg)
        for fun in sorted(docs):
            display_output('{0}:'.format(fun), 'text', self.opts)
            print(docs[fun])

    # TODO: move to mixin whenever we want a salt-wheel cli
    def run(self):
        '''
        Execute the runner sequence
        '''
        ret = {}
        if self.opts.get('doc', False):
            self.print_docs()
        else:
            try:
                low = {'fun': self.opts['fun']}
                args, kwargs = salt.minion.load_args_and_kwargs(
                    self.functions[low['fun']],
                    salt.utils.args.parse_input(self.opts['arg']),
                )
                low['args'] = args
                low['kwargs'] = kwargs

                async_pub = super(Runner, self).async(self.opts['fun'], low)
                # Run the runner!
                if self.opts.get('async', False):
                    log.info('Running in async mode. Results of this execution may '
                             'be collected by attaching to the master event bus or '
                             'by examing the master job cache, if configured. '
                             'This execution is running in pid {pid} under tag {tag}'.format(**async_pub))
                    exit(0)  # TODO: return or something? Don't like exiting...

                # output rets if you have some
                if not self.opts.get('quiet', False):
                    self.print_async_returns(async_pub['tag'])

            except salt.exceptions.SaltException as exc:
                ret = str(exc)
                if not self.opts.get('quiet', False):
                    print(ret)
                return ret
            log.debug('Runner return: {0}'.format(ret))
            return ret
