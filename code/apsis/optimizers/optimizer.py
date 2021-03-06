__author__ = 'Frederik Diehl'

from abc import ABCMeta, abstractmethod
from time import sleep
from apsis.utilities import logging_utils
import threading
import Queue

class Optimizer(object):
    """
    This defines a basic Optimizer interface.

    An optimizer contains an _experiment, which represents the last known state
     of the experiment. It can be updated using update, while the next
     candidates can be generated with get_next_candidates, which represent the
     actual work of the optimizer.
    Additionally, it contains an exit function, which can be used to cleanly
    exit the optimizer. Since the optimizer may well implement multicore or
    distributed architectures, it is necessary to cleanly exit.

    Parameters
    ----------
    SUPPORTED_PARAM_TYPES : list
        A list of the supported parameters for this optimizer. Not all
        parameters may be supported by any optimizer.
    _experiment : Experiment
        The current state of the experiment. Is used as a base for the the
        optimization.
    """
    __metaclass__ = ABCMeta

    SUPPORTED_PARAM_TYPES = []

    _experiment = None
    name = None
    _logger = None

    treat_failed = None

    def __init__(self, experiment, optimizer_params):
        """
        Initializes the optimizer.

        Parameters
        ----------
        experiment : Experiment
            The experiment representing the current state of the execution.
        optimizer_params : dict, optional
            Dictionary of the optimizer parameters. If None, some standard
            parameters will be assumed.
            One existing parameter is 'treat_failed', which changes the
            treatment of failed candidates. Possible is
                - 'ignore': Ignores the failed parameters
                - 'fixed_value': Changes all occurences of failed values
                    to a fixed value. Default value is 1e6 or 1e-6.
                - 'worst_mult': Changes all occurences of failed values to a
                    fixed multiplied of the worst result. Specifically, the
                    new value will be (worst_value - best_value) * x +
                    worst_value. The default. Default value is x=10.
            All of these can either be specified as strings (and use a
            standard value) or as tuples, in which case the first entry is
            treated as the string and the second as the value for the parameter.

        Raises
        ------
        ValueError
            Iff the experiment is not supported.
        """
        self._logger = logging_utils.get_logger(self)
        if not self._is_experiment_supported(experiment):
            raise ValueError("Experiment contains unsupported parameters. "
                             "Optimizer %s supports %s, experiment parameters "
                             "are %s." %(self.__class__.__name__,
                                         self.SUPPORTED_PARAM_TYPES,
                                         experiment.parameter_definitions))
        self._experiment = experiment
        if optimizer_params is None:
            optimizer_params = {}
        self.treat_failed = optimizer_params.get("treat_failed", "worst_mult")
        second_value = None
        if not isinstance(self.treat_failed, tuple):
            if self.treat_failed == "ignore":
                second_value = False
            elif self.treat_failed == "fixed_value":
                if self._experiment.minimization_problem:
                    second_value = 1e6
                else:
                    second_value = 1e-6
            elif self.treat_failed == "worst_mult":
                second_value = 2
            self.treat_failed = (self.treat_failed, second_value)

    def update(self, experiment):
        """
        Updates the experiment.

        Implementation note: This function (for the base class) only sets
        the new _experiment. Subclasses can call it to ensure correct setting
        of the experiment parameter.

        Parameters
        ----------
        experiment : Experiment
            The experiment representing the current state of the execution.

        Raises
        ------
        ValueError
            Iff the experiment is not supported.
        """
        if not self._is_experiment_supported(experiment):
            raise ValueError("Experiment contains unsupported parameters. "
                             "Optimizer %s supports %s, experiment parameters "
                             "are %s." %(self.__class__.__name__,
                                         self.SUPPORTED_PARAM_TYPES,
                                         experiment.parameter_definitions))
        self._experiment = experiment


    @abstractmethod
    def get_next_candidates(self, num_candidates=1):
        """
        Returns a number of candidates.

        Parameters
        ----------
        num_candidates : strictly positive int, optional
            The maximum number of candidates returned. Note that there may
            be less than that in the list.

        Returns
        -------
        candidates : list of candidates
            The list of candidates to evaluate next. May be None (which
            represents no current candidates being available), and may have
            between one and num_candidates candidates.
        """
        pass

    def exit(self):
        """
        Cleanly exits this optimizer.

        Note that, since optimizers may be of a multiprocessing or
        distributed nature, this function is important for stopping.

        Internal Note: This function, which will be inherited, does nothing. If
         an optimizer does not require another any other behaviour, it will not
         be necessary to redefine it.
        """
        pass

    def _is_experiment_supported(self, experiment):
        """
        Tests whether all parameter types in experiment are supported by this
        optimizer.

        Parameters
        ----------
        experiment : Experiment
            The experiment to test.

        Returns
        -------
        supported : bool
            False iff one or more of experiment's parameter definitions are not
            supported.
        """
        self._logger.debug("Testing whether experiment %s is supported.",
                           experiment)
        for name, pd in experiment.parameter_definitions.iteritems():
            if not self._is_supported_param_type(pd):
                self._logger.debug("It is not.")
                return False

        self._logger.debug("It is.")
        return True

    def _is_supported_param_type(self, param):
        """
        Tests whether a certain parameter is supported by the optimizer.

        Parameters
        ----------
        param :
            The parameter to be tested

        Result
        ------
        is_supported : bool
            True iff param is supported by this optimizer.
        """
        self._logger.debug("Testing whether param %s is supported.",
                           param)
        if isinstance(self.SUPPORTED_PARAM_TYPES, list):
            for sup in self.SUPPORTED_PARAM_TYPES:
                if isinstance(param, sup):
                    self._logger.debug("It is.")
                    return True

        self._logger.debug("It is not.")
        return False


class QueueBasedOptimizer(Optimizer):
    """
    This implements a queue-based optimizer.

    A queue-based optimizer is an abstraction of another optimizer. It works by
     putting the other optimizer into another process, then communicating
     with it via queues and a QueueBackend instance. This means easy
     deployability without having to change code.

    Internally, the QueueBackend puts new candidates onto the
    optimizer_out_queue, keeping it at min_candidates, until it receives a
    new update. In that case, all current candidates in the out_queue are
    deleted.

    Parameters
    ----------
    _optimizer_in_queue : Queue
        The queue with which you can send data (experiments) to the optimizer.
    _optimizer_out_queue : Queue
        The queue on which you can receive data.
    """
    _optimizer_in_queue = None
    _optimizer_out_queue = None

    _optimizer_process = None

    _manager = None

    _optimizer_class = None

    def __init__(self, optimizer_class, experiment, optimizer_params=None):
        """
        Initializes a new QueueBasedOptimizer class.

        Parameters
        ----------
        optimizer_class : an Optimizer subclass
            The class of optimizer this should abstract from. The optimizer is
            then initialized here.
        experiment : Experiment
            The experiment representing the current state of the execution.
        optimizer_params : dict, optional
            Dictionary of the optimizer parameters. If None, some standard
            parameters will be assumed.
            Supports the parameter "min_candidates", which sets the number
            of candidates that should be kept ready. Default is 5.
            Supports the parameter "update_time", which sets the minimum time
            in seconds between checking for updates. Default is 0.1s
        """
        self._logger = logging_utils.get_logger(self)
        self._logger.debug("Initializing new QueueBasedLogger. "
                           "optimizer_class is %s, experiment %s, "
                           "optimizer_params %s", optimizer_class,
                           experiment, optimizer_params)
        self._optimizer_in_queue = Queue.Queue()
        self._optimizer_out_queue = Queue.Queue()
        self._optimizer_class = optimizer_class
        self.SUPPORTED_PARAM_TYPES = optimizer_class.SUPPORTED_PARAM_TYPES

        self._logger.debug("Initialized queues. in_queue is %s, out_queue %s",
                           self._optimizer_in_queue, self._optimizer_out_queue)

        p = threading.Thread(target=dispatch_queue_backend,
                                    args=(optimizer_class, optimizer_params,
                                          experiment,
                                          self._optimizer_out_queue,
                                          self._optimizer_in_queue))
        p.start()
        self._logger.debug("Started thread.")
        super(QueueBasedOptimizer, self).__init__(experiment, optimizer_params)

    def get_next_candidates(self, num_candidates=1):
        self._logger.debug("Returning next %s candidates", num_candidates)
        next_candidates = []
        try:
            for i in range(num_candidates):
                new_candidate = self._optimizer_out_queue.get_nowait()
                next_candidates.append(new_candidate)
        except Queue.Empty:
            self._logger.debug("Queue of new candidates is empty.")
            pass
        self._logger.debug("Generated next_candidates %s", next_candidates)
        return next_candidates

    @property
    def name(self):
        if isinstance(self._optimizer_class, basestring):
            return self._optimizer_class
        else:
            return self._optimizer_class.name

    def update(self, experiment):
        self._logger.debug("Putting experiment %s into the queue",
                           experiment)
        self._optimizer_in_queue.put(experiment)

    def exit(self):
        """
        Also closes the optimizer.

        It does so by putting "exit" into the in_queue and closing both queues.
        """
        self._logger.debug("Exiting.")
        if self._optimizer_in_queue is not None:
            self._logger.debug("Put exit into the optimizer queue.")
            self._optimizer_in_queue.put("exit")


class QueueBackend(object):
    """
    This is the backend for QueueBasedOptimizer.

    It ensures there's a compatible request to the stored optimizer.

    Parameters
    ----------
    _experiment : Experiment
        The current state of the experiment.
    _out_queue : Queue
        The queue on which to put the candidates.
    _in_queue : Queue
        The queue on which to receive the new experiments.
    _optimizer : Optimizer
        The optimizer this abstracts from
    _min_candidates : int
        The minimum numbers of candidates to keep ready.
    _exited : bool
        Whether this process should exit (has seen the exit signal).
    """
    _experiment = None
    _out_queue = None
    _in_queue = None

    _optimizer = None

    _min_candidates = None
    _exited = None
    _update_time = None

    _logger = None

    def __init__(self, optimizer_class, experiment, out_queue, in_queue,
                 optimizer_params=None):
        """
        Initializes this backend.

        Parameters
        ----------
        optimizer_class : an Optimizer subclass
            The class of optimizer this should abstract from. The optimizer is
            then initialized here.
        experiment : Experiment
            The experiment representing the current state of the execution.
        optimizer_params : dict, optional
            Dictionary of the optimizer parameters. If None, some standard
            parameters will be assumed.
            Supports the parameter "min_candidates", which sets the number
            of candidates that should be kept ready.
        out_queue : Queue
            The queue on which to put the candidates.
        in_queue : Queue
            The queue on which to receive the new experiments.
        """
        self._logger = logging_utils.get_logger(self)
        self._logger.debug("Initializing queue backend. Parameters: "
                           "optimizer_class %s, experiment %s, out_queue %s, "
                           "in_queue %s, optimizer_params %s",
                           optimizer_class, experiment, out_queue, in_queue,
                           optimizer_params)

        self._out_queue = out_queue
        self._in_queue = in_queue
        if optimizer_params is None:
            optimizer_params = {}
        self._min_candidates = optimizer_params.get("min_candidates", 5)
        self._update_time = optimizer_params.get("update_time", 0.1)
        self._optimizer = optimizer_class(experiment, optimizer_params)
        self._exited = False
        self._experiment = experiment
        self._logger.debug("Had set the parameters to: out_queue is %s, "
                           "in_queue %s, optimizer_params %s, "
                           "min_candidates %s, update_time %s,"
                           " optimizer %s, exited %s, experiment %s",
                           out_queue, in_queue, optimizer_params,
                           self._min_candidates, self._update_time,
                           self._optimizer, self._exited, self._experiment)
        #multiprocessing.Process.__init__(self)

    def run(self):
        """
        The run function of this process, checking for new updates.

        Every _update_time seconds, it checks both the necessity of a new
        generation of candidates, and whether an update is necessary.

        It also makes sure all queues will be closed.
        """
        try:
            while not self._exited:
                self._check_generation()
                self._check_update()
                sleep(0.1)
        finally:
            pass

    def _check_update(self):
        """
        This checks for the availability of updates.

        Specifically, it does the following:
        If the in_queue is not empty (that is, there are one or more
        experiments available) it takes the last, most recently added. If
        one of the elements is "exit", it will exit instead.
        The latest experiment is then used to call the update function of the
        abstracted optimizer.
        Additionally, it will empty the out_queue, since we assume it has more,
        better information available.
        """
        new_update = None
        while not self._in_queue.empty():
            try:
                new_update = self._in_queue.get_nowait()
                self._logger.debug("Received new update: %s", new_update)
            except Queue.Empty:
                pass
            if new_update == "exit":
                self._logger.debug("Update received was exit.")
                self._exited = True
                return
        if new_update is not None:
            # clear the out queue. We'll soon have new information.
            try:
                while not self._out_queue.empty():
                    self._out_queue.get_nowait()
                self._logger.debug("Cleared out the update queue.")
            except Queue.Empty:
                pass
            self._experiment = new_update
            self._optimizer.update(self._experiment)
            self._logger.debug("Finished updating.")

    def _check_generation(self):
        """
        This checks whether new candidates should be generated.

        Specifically, it tests whether less than min_candidates are available
        in the out_queue. If so, it will (via optimizer.get_next_candidates)
        try to add min_candidates candidates.
        """
        try:
            if (self._out_queue.empty() or
                           self._out_queue.qsize < self._min_candidates):
                new_candidates = self._optimizer.get_next_candidates(
                    num_candidates=self._min_candidates)
                self._logger.debug("Needed to generate new candidates. "
                                   "Generated %s", new_candidates)
                if new_candidates is None:
                    return
                for c in new_candidates:
                    self._out_queue.put_nowait(c)
        except Queue.Full:
            return


def dispatch_queue_backend(optimizer_class, optimizer_params, experiment,
                           out_queue, in_queue):
    optimizer = QueueBackend(optimizer_class, experiment, out_queue,
                                 in_queue, optimizer_params)
    optimizer.run()
