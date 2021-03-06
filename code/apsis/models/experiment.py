__author__ = 'Frederik Diehl'

from apsis.models.candidate import Candidate
from apsis.models.parameter_definition import ParamDef
import copy
import uuid
import time
from apsis.utilities.param_def_utilities import dict_to_param_defs
import json
from apsis.models import candidate
from apsis.utilities import logging_utils


class Experiment(object):
    """
    An Experiment is a set of parameter definitions and multiple candidate
    evaluations thereon.

    Attributes
    ----------
    name : string
        The name of the experiment. This does not have to be unique, but is
        for human orientation.
    parameter_definitions : dict of ParamDefs
        A dictionary of ParamDef instances. These define the parameter space
        over which optimization is possible.
    minimization_problem : bool
        Defines whether the experiment's goal is to find a minimum result - for
        example when evaluating errors - or a maximum result - for example when
        evaluating scores.
    candidates_pending : list of Candidate instances
        These Candidate instances have been generated by an optimizer to be
        evaluated at the next possible time, but are not yet assigned to a
        worker.
    candidates_working : list of Candidate instances
        These Candidate instances are currently being evaluated by workers.
    candidates_finished : list of Candidate instances
        These Candidate instances have finished evaluated.
    best_candidate : Candidate instance
        The as of yet best Candidate instance found, according to the result.
    note : string, optional
        The note can be used to add additional human-readable information to
        the experiment.
    last_update_time : float
        The time the last update happened.
    """
    name = None

    parameter_definitions = None
    minimization_problem = None

    notes = None
    exp_id = None

    candidates_pending = None
    candidates_working = None
    candidates_finished = None

    best_candidate = None

    last_update_time = None

    _logger = None

    def __init__(self, name, parameter_definitions, exp_id=None, notes=None,
                 minimization_problem=True,):
        """
        Initializes an Experiment with a certain parameter definition.

        All of the Candidate lists are set to empty lists, representing an
        experiment with no work done.

        Parameters
        ----------
        name : string
            The name of the experiment. This does not have to be unique, but is
            for human orientation.

        parameter_definitions : dict of ParamDef
            Defines the parameter space of the experiment. Each entry of the
            dictionary has to be a ParamDef, and it is that space over which
            optimization will occur.
        minimization_problem : bool, optional
            Defines whether the experiment's goal is to find a minimum result - for
            example when evaluating errors - or a maximum result - for example when
            evaluating scores. Is True by default.
        notes : string or None, optional
            The note can be used to add additional human-readable information to
            the experiment.
        Raises
        ------
        ValueError :
            Iff parameter_definitions are not a dictionary.
        """
        self._logger = logging_utils.get_logger(self)
        self._logger.debug("Initializing new experiment. name: %s, "
                           "param_definition: %s, exp_id %s, notes %s, "
                           "minimization_problem %s", name,
                           parameter_definitions, exp_id, notes,
                           minimization_problem)
        self.name = name
        if exp_id is None:
            exp_id = uuid.uuid4().hex
            self._logger.debug("Had to create new exp_id, is %s", exp_id)
        self.exp_id = exp_id
        if not isinstance(parameter_definitions, dict):
            self._logger.error("parameter_definitions are not a dict but %s."
                             %parameter_definitions)
            raise ValueError("parameter_definitions are not a dict but %s."
                             %parameter_definitions)
        for p in parameter_definitions:
            if not isinstance(parameter_definitions[p], ParamDef):
                self._logger.error("Parameter definition of %s is not a "
                                   "ParamDef but %s."
                                   %(p, parameter_definitions[p]))

                raise ValueError("Parameter definition of %s is not a ParamDef"
                                 "but %s." %(p, parameter_definitions[p]))
        self.parameter_definitions = parameter_definitions

        self.minimization_problem = minimization_problem

        self.candidates_finished = []
        self.candidates_pending = []
        self.candidates_working = []

        self.last_update_time = time.time()

        self.notes = notes
        self._logger.debug("Initialization of new experiment finished.")

    def add_finished(self, candidate):
        """
        Announces a Candidate instance to be finished evaluating.

        This moves the Candidate instance to the candidates_finished list and
        updates the best_candidate.

        Parameters
        ----------
        candidate : Candidate
            The Candidate to be added to the finished list.

        Raises
        ------
        ValueError :
            Iff candidate is not a Candidate object.
        """
        self._logger.debug("Adding finished candidate %s", candidate)
        self._check_candidate(candidate)
        if candidate in self.candidates_pending:
            self.candidates_pending.remove(candidate)
        if candidate in self.candidates_working:
            self.candidates_working.remove(candidate)
        if candidate in self.candidates_finished:
            self.candidates_finished.remove(candidate)

        cur_time = time.time()
        candidate.last_update_time = cur_time
        self.last_update_time = cur_time
        self.candidates_finished.append(candidate)
        self._update_best()
        self._logger.debug("Added finished candidate %s", candidate)

    def add_pending(self, candidate):
        """
        Adds a new pending Candidate object to be evaluated.

        This function should be used when a new pending candidate is supposed
        to be evaluated. If an old Candidate should be updated as just pausing,
        use the add_pausing function.

        Parameters
        ----------
        candidate : Candidate
            The Candidate instance that is supposed to be evaluated soon.

        Raises
        ------
        ValueError :
            Iff candidate is no Candidate object.
        """
        self._logger.debug("Adding pending candidate %s", candidate)
        self._check_candidate(candidate)
        if candidate in self.candidates_pending:
            self.candidates_pending.remove(candidate)
        if candidate in self.candidates_working:
            self.candidates_working.remove(candidate)
        if candidate in self.candidates_finished:
            self.candidates_finished.remove(candidate)

        cur_time = time.time()
        candidate.last_update_time = cur_time
        self.last_update_time = cur_time

        self.candidates_pending.append(candidate)

        self._update_best()
        self._logger.debug("Added pending candidate %s", candidate)

    def add_working(self, candidate):
        """
        Updates the experiment to now start working on candidate.

        This updates candidates_working list and the candidates_pending list
        if candidate is in the candidates_pending list.

        Parameters
        ----------
        candidate : Candidate
            The Candidate instance that is currently being worked on.

        Raises
        ------
        ValueError :
            Iff candidate is no Candidate object.
        """
        self._logger.debug("Added working candidate %s", candidate)
        self._check_candidate(candidate)
        if candidate in self.candidates_pending:
            self.candidates_pending.remove(candidate)
        if candidate in self.candidates_working:
            self.candidates_working.remove(candidate)
        if candidate in self.candidates_finished:
            self.candidates_finished.remove(candidate)

        cur_time = time.time()
        candidate.last_update_time = cur_time
        self.last_update_time = cur_time

        self.candidates_working.append(candidate)
        self._update_best()
        self._logger.debug("Added working candidate %s", candidate)

    def add_pausing(self, candidate):
        """
        Updates the experiment that work on candidate has been paused.

        This updates candidates_pending list and the candidates_working list
        if it contains the candidate.

        Parameters
        ----------
        candidate : Candidate
            The Candidate instance that is currently paused.

        Raises
        ------
        ValueError :
            Iff candidate is no Candidate object.

        """
        self._logger.debug("Pausing candidate %s", candidate)
        self._check_candidate(candidate)
        if candidate in self.candidates_working:
            self.candidates_working.remove(candidate)
        if candidate in self.candidates_pending:
            self.candidates_pending.remove(candidate)
        if candidate in self.candidates_working:
            self.candidates_working.remove(candidate)
        if candidate in self.candidates_finished:
            self.candidates_finished.remove(candidate)

        cur_time = time.time()
        candidate.last_update_time = cur_time
        self.last_update_time = cur_time

        self.candidates_pending.append(candidate)
        self._update_best()
        self._logger.debug("Pausing candidate %s", candidate)

    def better_cand(self, candidateA, candidateB):
        """
        Determines whether CandidateA is better than candidateB in the context
        of this experiment.
        This is done as follows:
        If candidateA's result is None or it failed, it is not better.
        If candidateB's result is None or it failed, it is better.
        If it is a minimization problem and the result is smaller than B's, it
        is better. Corresponding for being a maximization problem.


        Parameters
        ----------
        candidateA : Candidate
            The candidate which should be better.
        candidateB : Candidate
            The baseline candidate.

        Returns
        -------
        result : bool
            True iff A is better than B.

        Raises
        ------
        ValueError :
            If candidateA or candidateB are no Candidates.
        """
        self._logger.debug("Checking better candidate, %s or %s", candidateA,
                           candidateB)
        if not isinstance(candidateA, Candidate) and candidateA is not None:
            raise ValueError("candidateA is %s, but no Candidate instance."
                             %str(candidateA))
        if not isinstance(candidateB, Candidate) and candidateB is not None:
            raise ValueError("candidateB is %s, but no Candidate instance."
                             %str(candidateB))

        if candidateA is None:
            self._logger.debug("candidateA is None; returning False")
            return False
        if candidateB is None:
            self._logger.debug("candidateB is None; returning True")
            return True

        if not self._check_candidate(candidateA):
            raise ValueError("candidateA is not valid.")
        if not self._check_candidate(candidateB):
            raise ValueError("candidateB is not valid.")

        a_result = candidateA.result
        b_result = candidateB.result

        comparison = None
        if a_result is None or candidateA.failed:
            comparison = False
        elif b_result is None or candidateB.failed:
            comparison = True
        elif self.minimization_problem:
            if a_result < b_result:
                comparison = True
            else:
                comparison = False
        else:
            if a_result > b_result:
                comparison = True
            else:
                comparison = False
        self._logger.debug("Comparison result: %s", comparison)
        return comparison

    def warp_pt_in(self, params):
        """
        Warps in a point.

        Parameters
        ----------
        params : dict of string keys
            The point to warp in

        Returns
        -------
        warped_in : dict of string keys
            The warped-in parameters.
        """
        self._logger.debug("Warping point in. Params: %s", params)
        warped_in = {}
        for name, value in params.iteritems():
            warped_in[name] = self.parameter_definitions[name].warp_in(value)
        self._logger.debug("Warped-in parameters: %s", warped_in)
        return warped_in

    def warp_pt_out(self, params):
        """
        Warps out a point.

        Parameters
        ----------
        params : dict of string keys
            The point to warp out

        Returns
        -------
        warped_out : dict of string keys
            The warped-out parameters.
        """
        self._logger.debug("Warping point out. params: %s", params)
        warped_out = {}
        for name, value in params.iteritems():
            warped_out[name] = self.parameter_definitions[name].warp_out(value)
        self._logger.debug("Warped-out parameters: %s", warped_out)
        return warped_out

    def clone(self):
        """
        Create a deep copy of this experiment and return it.

        Returns
        -------
            copied_experiment : Experiment
                A deep copy of this experiment.
        """
        self._logger.debug("Cloning experiment.")
        copied_experiment = copy.deepcopy(self)
        self._logger.debug("Cloned experiment is %s", copied_experiment)
        return copied_experiment

    def _check_candidate(self, cand):
        """
        Checks whether cand is valid for this experiment.

        This checks the existence of all parameter definitions and that all
        values are acceptable.

        Parameter
        ---------
        cand : Candidate
            Candidate to check

        """
        if not isinstance(cand, Candidate):
            self._logger.error("cand is not an instance of Candidate but is"
                             "%s", cand)
            raise ValueError("cand is not an instance of Candidate but is"
                             "%s" % cand)
        if not set(cand.params.keys()) == set(self.parameter_definitions.keys()):
            self._logger.error("cand %s is not valid.", cand)
            raise ValueError("cand %s is not valid." % cand)

        for k in cand.params:
            if not self.parameter_definitions[k].\
                    is_in_parameter_domain(cand.params[k]):
                self._logger.error("cand %s is not valid.", cand)
                raise ValueError("cand %s is not valid." % cand)
        return True

    def _check_param_dict(self, param_dict):
        """
        Checks whether parameter dictionary is valid for this experiment.

        This checks the existence of all parameter definitions and that all
        values are acceptable.

        Parameter
        ---------
        param_dict : dict with string keys
            Dictionary to check

        Returns
        -------
        acceptable : bool
            True iff the dictionary is valid
        """
        self._logger.debug("Checking parameter dictionary %s", param_dict)
        if not set(param_dict.keys()) == set(self.parameter_definitions.keys()):
            self._logger.debug("Returned false due to keys not being "
                               "identical.")
            return False

        for k in param_dict:
            if not self.parameter_definitions[k].is_in_parameter_domain(param_dict[k]):
                self._logger.debug("Returned false due to param_def %s not"
                                   "being in parameter domain %s", k,
                                   self.parameter_definitions[k])
                return False
        self._logger.debug("Returning True; dict acceptable.")
        return True

    def to_dict(self):
        """
        Generates a dictionary describing the current state of the experiment.

        This dictionary contains the following keys/value pairs:
            - "name": The name of the experiment
            - "parameter_definition": The parameter definition. Contains, for
                each parameter, a key/value pair of the parameter name and the
                dictionary as defined by param_def.to_dict().
            - "mimization_problem": Boolean. If true, the problem is one we
                want to minimize. If false, it's one we want to maximize.
            - "notes": Notes the user has entered for the experiment.
            - "exp_id": The ID of the experiment.
            - One list each for candidates_finished, -_pending and -_working.
                Contains, for each candidate in the respective list, a
                dictionary as defined by Candidate.to_dict().
            - "best_candidate": The best candidate or None.

        Returns
        -------
            dict : dict
                Dictionary as defined above.

        """
        self._logger.debug("Generating experiment dictionary.")
        param_defs = {}
        for k in self.parameter_definitions:
            param_defs[k] = self.parameter_definitions[k].to_dict()
        cand_dict_finished = [c.to_dict() for c in self.candidates_finished]
        cand_dict_pending = [c.to_dict() for c in self.candidates_pending]
        cand_dict_working = [c.to_dict() for c in self.candidates_working]

        result_dict = {"name": self.name,
                "parameter_definitions": param_defs,
                "minimization_problem": self.minimization_problem,
                "notes": self.notes,
                "exp_id": self.exp_id,
                "candidates_finished": cand_dict_finished,
                "candidates_pending": cand_dict_pending,
                "candidates_working": cand_dict_working,
                "last_update_time": self.last_update_time
                }
        if self.best_candidate is not None:
            result_dict["best_candidate"] = self.best_candidate.to_dict()
        else:
            result_dict["best_candidate"] = None
        self._logger.debug("Final dictionary: %s", result_dict)
        return result_dict

    def _update_best(self):
        self._logger.debug("Updating best candidate.")
        best_candidate = None
        for c in self.candidates_finished:
            if self.better_cand(c, best_candidate):
                best_candidate = c
                self._logger.debug("Found new better candidate: %s", c)
        self._logger.debug("Best candidate now %s", best_candidate)
        self.best_candidate = best_candidate

    def write_state_to_file(self, path):
        self._logger.debug("Writing stats to %s", path)
        with open(path + '/experiment.json', 'w') as outfile:
            json.dump(self.to_dict(), outfile)



def from_dict(d):
    experiment_logger = logging_utils.get_logger("models.Experiment")
    experiment_logger.log(5, "Reconstructing experiment from dict %d", d)
    name = d["name"]
    param_defs = dict_to_param_defs(d["parameter_definitions"])
    minimization_problem = d["minimization_problem"]
    notes = d["notes"]
    exp_id = d["exp_id"]
    experiment_logger.debug("Reconstructed attributes.")
    cand_dict_finished = d["candidates_finished"]
    cands_finished = []
    for c in cand_dict_finished:
        cands_finished.append(candidate.from_dict(c))
    cand_dict_pending = d["candidates_pending"]
    cands_pending = []
    for c in cand_dict_pending:
        cands_pending.append(candidate.from_dict(c))
    cand_dict_working = d["candidates_working"]
    cands_working = []
    for c in cand_dict_working:
        cands_working.append(candidate.from_dict(c))
    experiment_logger.log(5, "Reconstructed candidates.")
    best_candidate = d["best_candidate"]

    exp = Experiment(name, param_defs, exp_id, notes, minimization_problem)

    exp.candidates_finished = cands_finished
    exp.candidates_pending = cands_pending
    exp.candidates_working = exp.candidates_working
    exp._update_best()
    exp.last_update_time = d.get("last_update_time", time.time())

    experiment_logger.log(5, "Finished reconstruction. Exp is %s.", exp)

    return exp