# Copyright 2013 Hynek Schlawack
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Logger wrapper and helper class.
"""

from __future__ import absolute_import, division, print_function

from structlog._compat import string_types
from structlog._exc import DropEvent


class BoundLoggerBase(object):
    """
    Immutable context carrier.

    Doesn't do any actual logging; examples for useful subclasses are:

        - the generic :class:`BoundLogger` that can wrap anything,
        - :class:`structlog.twisted.BoundLogger`,
        - and :class:`structlog.stdlib.BoundLogger`.

    See also :doc:`custom-wrappers`.
    """
    _logger = None
    """
    Wrapped logger.

    .. note::

        Despite underscore available **read-only** to custom wrapper classes.

        See also :doc:`custom-wrappers`.
    """

    def __init__(self, logger, processors, context):
        self._logger = logger
        self._processors = processors
        self._context = context

    def __repr__(self):
        return '<{0}(context={1!r}, processors={2!r})>'.format(
            self.__class__.__name__,
            self._context,
            self._processors,
        )

    def __eq__(self, other):
        try:
            if self._context == other._context:
                return True
            else:
                return False
        except AttributeError:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def bind(self, **new_values):
        """
        Return a new logger with *new_values* added to the existing ones.

        :rtype: `self.__class__`
        """
        return self.__class__(
            self._logger,
            self._processors,
            self._context.__class__(self._context, **new_values)
        )

    def unbind(self, *keys):
        """
        Return a new logger with *keys* removed from the context.

        :raises KeyError: If the key is not part of the context.

        :rtype: `self.__class__`
        """
        bl = self.bind()
        for key in keys:
            del bl._context[key]
        return bl

    def new(self, **new_values):
        """
        Clear context and binds *initial_values* using :func:`bind`.

        Only necessary with dict implementations that keep global state like
        those wrapped by :func:`structlog.threadlocal.wrap_dict` when threads
        are re-used.

        :rtype: `self.__class__`
        """
        self._context.clear()
        return self.bind(**new_values)

    # Helper methods for sub-classing concrete BoundLoggers.

    def _process_event(self, method_name, event, event_kw):
        """
        Combines creates an `event_dict` and runs the chain.

        Call it to combine your *event* and *context* into an event_dict and
        process using the processor chain.

        :param str method_name: The name of the logger method.  Is passed into
            the processors.
        :param event: The event -- usually the first positional argument to a
            logger.
        :param event_kw: Additional event keywords.  For example if someone
            calls ``log.msg('foo', bar=42)``, *event* would to be ``'foo'``
            and *event_kw* ``{'bar': 42}``.
        :raises: :class:`structlog.DropEvent` if log entry should be dropped.
        :rtype: `tuple` of `(*args, **kw)`

        .. note::

            Despite underscore available to custom wrapper classes.

            See also :doc:`custom-wrappers`.
        """
        event_dict = self._context.copy()
        event_dict.update(**event_kw)
        if event:
            event_dict['event'] = event
        for proc in self._processors:
            event_dict = proc(self._logger, method_name, event_dict)
        if isinstance(event_dict, string_types):
            return (event_dict,), {}
        else:
            return event_dict

    def _proxy_to_logger(self, method_name, event=None, *event_args,
                         **event_kw):
        """
        Run processor chain on event & call *method_name* on wrapped logger.

        DRY convenience method that runs :func:`_process_event`, takes care of
        handling :exc:`structlog.DropEvent`, and finally calls *method_name* on
        :attr:`_logger` with the result.

        :param str method_name: The name of the method that's going to get
            called.  Technically it should be identical to the method the
            user called because it also get passed into processors.
        :param event: The event -- usually the first positional argument to a
            logger.
        :param event_kw: Additional event keywords.  For example if someone
            calls ``log.msg('foo', bar=42)``, *event* would to be ``'foo'``
            and *event_kw* ``{'bar': 42}``.

        .. note::

            Despite underscore available to custom wrapper classes.

            See also :doc:`custom-wrappers`.
        """
        try:
            args, kw = self._process_event(method_name, event, event_kw)
            args = args[:] + event_args
            return getattr(self._logger, method_name)(*args, **kw)
        except DropEvent:
            return
