# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import eventlet
import mock
from oslo_config import cfg
from oslo_service import threadgroup

from senlin.engine.actions import base as actionm
from senlin.engine import scheduler
from senlin.tests.unit.common import base
from senlin.tests.unit.common import utils


class DummyThread(object):

    def __init__(self, function, *args, **kwargs):
        self.function = function

    def link(self, callback, *args):
        callback(self, *args)


class DummyThreadGroup(object):

    def __init__(self):
        self.threads = []

    def add_timer(self, interval, callback, initial_delay=None,
                  *args, **kwargs):
        self.threads.append(callback)

    def stop_timers(self):
        pass

    def add_thread(self, callback, *args, **kwargs):
        callback = args[1]
        self.threads.append(callback)
        return DummyThread()

    def stop(self, graceful=False):
        pass

    def wait(self):
        pass


class SchedulerTest(base.SenlinTestCase):

    def setUp(self):
        super(SchedulerTest, self).setUp()
        self.fake_tg = DummyThreadGroup()

        self.mock_tg = self.patchobject(threadgroup, 'ThreadGroup')
        self.mock_tg.return_value = self.fake_tg

        self.context = utils.dummy_context()

    def test_create(self):
        tgm = scheduler.ThreadGroupManager()
        self.assertEqual({}, tgm.workers)

        mock_group = mock.Mock()
        self.mock_tg.return_value = mock_group
        tgm = scheduler.ThreadGroupManager()
        mock_group.add_timer.assert_called_once_with(
            cfg.CONF.periodic_interval,
            tgm._service_task)

    def test_start(self):
        def f():
            pass

        mock_group = mock.Mock()
        self.mock_tg.return_value = mock_group

        tgm = scheduler.ThreadGroupManager()
        tgm.start(f)

        mock_group.add_thread.assert_called_once_with(f)

    def test_start_action(self):
        mock_group = mock.Mock()
        self.mock_tg.return_value = mock_group

        tgm = scheduler.ThreadGroupManager()
        tgm.start_action(self.context, '0123', '4567')

        mock_group.add_thread.assert_called_once_with(actionm.ActionProc,
                                                      self.context,
                                                      '0123', '4567')
        mock_thread = mock_group.add_thread.return_value
        self.assertEqual(mock_thread, tgm.workers['0123'])
        mock_thread.link.assert_called_once_with(mock.ANY, self.context,
                                                 '0123')

    def test_cancel_action(self):
        mock_action = mock.Mock()
        mock_load = self.patchobject(actionm.Action, 'load',
                                     return_value=mock_action)
        tgm = scheduler.ThreadGroupManager()
        tgm.cancel_action(self.context, 'action0123')

        mock_load.assert_called_once_with(self.context, 'action0123')
        mock_action.signal.assert_called_once_with(self.context,
                                                   mock_action.SIG_CANCEL)

    def test_suspend_action(self):
        mock_action = mock.Mock()
        mock_load = self.patchobject(actionm.Action, 'load',
                                     return_value=mock_action)
        tgm = scheduler.ThreadGroupManager()
        tgm.suspend_action(self.context, 'action0123')

        mock_load.assert_called_once_with(self.context, 'action0123')
        mock_action.signal.assert_called_once_with(self.context,
                                                   mock_action.SIG_SUSPEND)

    def test_resume_action(self):
        mock_action = mock.Mock()
        mock_load = self.patchobject(actionm.Action, 'load',
                                     return_value=mock_action)
        tgm = scheduler.ThreadGroupManager()
        tgm.resume_action(self.context, 'action0123')

        mock_load.assert_called_once_with(self.context, 'action0123')
        mock_action.signal.assert_called_once_with(self.context,
                                                   mock_action.SIG_RESUME)

    def test_add_timer(self):
        def f():
            pass

        tgm = scheduler.ThreadGroupManager()
        tgm.add_timer(10, f)

        # The first element is the '_service_task'
        self.assertEqual(2, len(self.fake_tg.threads))
        self.assertEqual(f, self.fake_tg.threads[1])

    def test_stop_timer(self):
        mock_group = mock.Mock()
        self.mock_tg.return_value = mock_group

        tgm = scheduler.ThreadGroupManager()
        tgm.stop_timers()
        mock_group.stop_timers.assert_called_once_with()

    def test_stop(self):
        def f():
            pass

        mock_group = mock.Mock()
        self.mock_tg.return_value = mock_group
        tgm = scheduler.ThreadGroupManager()
        mock_group.threads = [
            DummyThread(tgm._service_task),
            DummyThread(f)
        ]
        tgm.start(f)

        tgm.stop()

        mock_group.stop.assert_called_once_with(False)
        mock_group.wait.assert_called_once_with()

    def test_reschedule(self):
        action = mock.Mock()
        action.id = '0123'
        mock_sleep = self.patchobject(eventlet, 'sleep')

        scheduler.reschedule(action)
        mock_sleep.assert_called_once_with(1)
        mock_sleep.reset_mock()

        scheduler.reschedule(action, None)
        self.assertEqual(0, mock_sleep.call_count)

    def test_sleep(self):
        mock_sleep = self.patchobject(eventlet, 'sleep')
        scheduler.sleep(1)
        mock_sleep.assert_called_once_with(1)