"""
Usage:
    psiturk_shell
    psiturk_shell setup_example
    psiturk_shell dashboard

"""
import sys
import re
import time

from cmd2 import Cmd
from docopt import docopt, DocoptExit
import readline

from amt_services import MTurkServices
from version import version_number
from psiturk_config import PsiturkConfig
import experiment_server_controller as control
import dashboard_server as dbs

#Escape sequences for display
def colorize(target, color):
    colored = ''
    if color == 'purple':
        colored = '\033[95m' + target
    elif color == 'cyan':
        colored = '\033[96m' + target
    elif color == 'darkcyan':
        colored = '\033[36m' + target
    elif color == 'blue':
        colored = '\033[93m' + target
    elif color == 'green':
        colored = '\033[92m' + target
    elif color == 'yellow':
        colored = '\033[93m' + target
    elif color == 'red':
        colored = '\033[91m' + target
    elif color == 'white':
        colored = '\033[37m' + target
    elif color == 'bold':
        colored = '\033[1m' + target
    elif color == 'underline':
        colored = '\033[4m' + target
    return colored + '\033[0m'

# decorator function borrowed from docopt
def docopt_cmd(func):
    """
    This decorator is used to simplify the try/except block and pass the result
    of the docopt parsing to the called action.
    """
    def fn(self, arg):
        try:
            opt = docopt(fn.__doc__, arg)
        except DocoptExit as e:
            # The DocoptExit is thrown when the args do not match.
            # We print a message to the user and the usage block.
            print('Invalid Command!')
            print(e)
            return
        except SystemExit:
            # The SystemExit exception prints the usage for --help
            # We do not need to do the print here.
            return
        return func(self, opt)
    fn.__name__ = func.__name__
    fn.__doc__ = func.__doc__
    fn.__dict__.update(func.__dict__)
    return fn



class Psiturk_Shell(Cmd):


    def __init__(self, config, services, server):
        Cmd.__init__(self)
        self.config = config
        self.server = server
        self.services = services
        self.sandbox = self.config.getboolean('HIT Configuration', 'using_sandbox')
        self.sandboxHITs = 0
        self.liveHITs = 0
        self.check_hits()
        self.color_prompt()
        self.intro = colorize('psiTurk version ' + version_number + \
                     '\nType "help" for more information.', 'green')

    def color_prompt(self):
        prompt =  '[' + colorize( 'psiTurk', 'bold')
        serverSring = ''
        server_status = self.server.is_server_running()
        if server_status == 'yes':
            serverString = colorize('on', 'green')
        elif server_status == 'no':
            serverString =  colorize('off', 'red')
        elif server_status == 'maybe':
            serverString = colorize('wait', 'yellow')
        prompt += ' server:' + serverString
        if self.sandbox:
            prompt += ' mode:' + colorize('sdbx', 'bold')
        else:
            prompt += ' mode:' + colorize('live', 'bold')
        if self.sandbox:
            prompt += ' #HITs:' + str(self.sandboxHITs)
        else:
            prompt += ' #HITs:' + str(self.liveHITs)
        prompt += ']$ '
        self.prompt =  prompt

    def onecmd_plus_hooks(self, line):
        if not line:
            return self.emptyline()
        return Cmd.onecmd_plus_hooks(self, line)


    def postcmd(self, stop, line):
        self.color_prompt()
        return Cmd.postcmd(self, stop, line)

    def emptyline(self):
        self.color_prompt()

    @docopt_cmd
    def do_mode(self, arg):
        """        
        Usage: mode
               mode <which>
        """
        if arg['<which>'] is None:
            if self.sandbox:
                arg['<which>'] = 'live'
            else:
                arg['<which>'] = 'sandbox'
        if arg['<which>']=='live':
            self.sandbox = False
            self.config.set('HIT Configuration', 'using_sandbox', False)
            self.check_hits()
            print 'Entered ' + colorize('live', 'bold') + ' mode'
        else:
            self.sandbox = True
            self.config.set('HIT Configuration', 'using_sandbox', True)
            self.check_hits()
            print 'Entered ' + colorize('sandbox', 'bold') + ' mode'
        

    @docopt_cmd
    def do_dashboard(self, arg):
        """
        Usage: dashboard [options]

        -i <address>, --ip <address>    IP to run dashboard on. [default: localhost].
        -p <num>, --port <num>          Port to run dashboard on. [default: 22361].
        """
        arg['--port'] = int(arg['--port'])
        dbs.launch(ip=arg['--ip'], port=arg['--port'])

    def do_version(self, arg):
        print 'psiTurk version ' + version_number

    def do_print_config(self, arg):
        f = open('config.txt', 'r')
        for line in f:
            sys.stdout.write(line)

    def do_status(self, arg):
        server_status = self.server.is_server_running()
        if server_status == 'yes':
            print 'Server: ' + colorize('currently online', 'green')
        elif server_status == 'no':
            print 'Server: ' + colorize('currently offline', 'red')
        elif server_status == 'maybe':
            print 'Server: ' + colorize('please wait', 'yellow')
        self.check_hits()
        if self.sandbox:
            print 'AMT worker site - ' + colorize('sandbox', 'bold') +  ': ' + str(self.sandboxHITs) + ' HITs available'
        else:
            print 'AMT worker site - ' + colorize('live', 'bold') + ': ' + str(self.liveHITs) + ' HITs available'

    def check_hits(self):
        hits = self.services.get_active_hits()
        if hits:
            if self.sandbox:
                self.sandboxHITs = len(hits)
            else:
                self.liveHITs = len(hits)
 
    @docopt_cmd
    def do_create_hit(self, arg):
        """
        Usage: create_hit
               create_hit <where> <numWorkers> <reward> <duration>
        """
        interactive = False
        if arg['<where>'] is None:
            interactive = True
            r = raw_input('[' + colorize('s', 'bold') +
                          ']andbox or [' + colorize('l', bold) 
                           + ']ive? ')
            if r == 's':
                arg['<where>'] = 'sandbox'
            elif r == 'l':
                arg['<where>'] = 'live'
        if arg['<where>'] != 'sandbox' and arg['<where>'] != 'live':
            print '*** invalid experiment location'
            return
        if interactive:
            arg['<numWorkers>'] = raw_input('number of participants? ')
        try:
            int(arg['<numWorkers>'])
        except ValueError:

            print '*** number of participants must be a whole number'
            return
        if int(arg['<numWorkers>']) <= 0:
            print '*** number of participants must be greater than 0'
            return
        if interactive:
            arg['<reward>'] = raw_input('reward per HIT? ')
        p = re.compile('\d*.\d\d')
        m = p.match(arg['<reward>'])

        if m is None:
            print '*** reward must have format [dollars].[cents]'
            return
        if interactive:
            arg['<duration>'] = raw_input('duration of hit (in hours)? ')
        try:
            int(arg['<duration>'])
        except ValueError:
            print '*** duration must be a whole number'
            return
        if int(arg['<duration>']) <= 0:
            print '*** duration must be greater than 0'
            return
        if arg['<where>'] == 'live':
            self.config.set('HIT Configuration', 'using_sandbox', False)
            self.sandbox = False
        else:
            self.config.set('HIT Configuration', 'using_sandbox', True)
            self.sandbox = True
        self.config.set('HIT Configuration', 'max_assignments',
                        arg['<numWorkers>'])
        self.config.set('HIT Configuration', 'reward', arg['<reward>'])
        self.config.set('HIT Configuration', 'duration', arg['<duration>'])
        self.services.create_hit()
        if self.sandbox:
            self.sandboxHITs += 1
        else:
            self.liveHITs += 1
        #print results
        total = float(arg['<numWorkers>']) * float(arg['<reward>'])
        fee = total / 10
        total = total + fee
        print '*****************************'
        print '  Creating HIT on \'' + arg['<where>'] + '\''
        print '    Max workers: ' + arg['<numWorkers>']
        print '    Reward: $' + arg['<reward>']
        print '    Duration: ' + arg['<duration>'] + ' hours'
        print '    Fee: $%.2f' % fee
        print '    ________________________'
        print '    Total: $%.2f' % total

    def do_setup_example(self, arg):
        import setup_example as se
        se.setup_example()

    def do_launch_server(self, arg):
        self.server.startup()
        while self.server.is_server_running() != 'yes':
            time.sleep(1)
            

    def do_shutdown_server(self, arg):
        self.server.shutdown()
        while self.server.is_server_running() != 'no':
            time.sleep(1)

    def do_restart_server(self, arg):
        self.server.restart()

    def do_get_workers(self, arg):
        workers = self.services.get_workers()
        if not workers:
            print colorize('failed to get workers', 'red')
        else:
            print self.services.get_workers()

    @docopt_cmd
    def do_approve_worker(self, arg):
        """
        Usage: approve_worker (--all | <assignment_id> ...)
        Options:
        --all        approve all completed workers

        """
        if arg['--all']:
            workers = self.services.get_workers()
            for worker in workers:
                success = self.services.approve_worker(worker['assignmentId'])
                if success:
                    print 'approved ' + arg['<assignment_id>']
                else:
                    print '*** failed to approve ' + arg['<assignment_id>']
        else:
            for assignmentID in arg['<assignment_id>']:
                success = self.services.approve_worker(assignmentID)
                if success:
                    print 'approved ' + arg['<assignment_id>']
                else:
                    print '*** failed to approve ' + arg['<assignment_id>']


    @docopt_cmd
    def do_reject_worker(self, arg):
        """
        Usage: reject_worker <assignment_id> ...
        """
        for assignmentID in arg['<assignment_id>']:
            success = self.services.reject_worker(assignmentID)
            if success:
                print 'rejected ' + arg['<assignment_id>']
            else:
                print  '*** failed to reject ' + arg['<assignment_id>']


    def do_check_balance(self, arg):
        print self.services.check_balance()


    def do_get_active_hits(self, arg):
        hits_data = self.services.get_active_hits()
        if not hits_data:
            print '*** failed to retrieve active hits'
        else:
            print hits_data

    @docopt_cmd
    def do_extend_hit(self, arg):
        """
        Usage: extend_hit <HITid> [options]

        -a <number>, --assignments <number>    Increase number of assignments on HIT
        -e <time>, --expiration <time>         Increase expiration time on HIT (hours)
        """
        self.services.extend_hit(self, arg['<HITid>'], arg['--assignments'], 
                            arg['--expiration'])

    @docopt_cmd
    def do_expire_hit(self, arg):
        """
        Usage: expire_hit <HITid>
        """
        self.services.expire_hit(arg['<HITid>'])
        if self.sandbox:
            self.sandboxHITs -= 1
        else:
            self.liveHITs -= 1

def run():
    opt = docopt(__doc__, sys.argv[1:])
    config = PsiturkConfig()
    config.load_config()
    services = MTurkServices(config)
    server = control.ExperimentServerController(config)
    shell = Psiturk_Shell(config, services, server)
    shell.cmdloop()