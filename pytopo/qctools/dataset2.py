""" A module to make working with the qcodes v2 dataset a bit more
convenient.

Maintainer: Wolfgang Pfaff <wolfgangpfff@gmail.com>
"""
import time
import qcodes as qc
from qcodes.dataset.data_set import DataSet
from qcodes.dataset.experiment_container import load_experiment_by_name, \
    new_experiment
# from qcodes.dataset.sqlite_base import transaction, one
try:
    from qcodes.dataset.sqlite_base import transaction, one
except ModuleNotFoundError:
    from qcodes.dataset.sqlite.connection import transaction
    from qcodes.dataset.sqlite.query_helpers import one


def select_experiment(exp_name, sample_name):
    """
    Convenience function that will check if the experiment/sample
    combination already exists in the current database. If so,
    it'll return the existing one. Otherwise it will create a new
    one and return that.

    Potential issue: if multiple experiments with the same
    experiment/sample combination exist, our detection method will
    fail, and another copy of this combination will be created.
    """
    try:
        exp = load_experiment_by_name(exp_name, sample_name)
    except ValueError:
        exp = new_experiment(exp_name, sample_name)
    return exp


def get_run_timestamp(run_id):
    DB = qc.config["core"]["db_location"]

    d = DataSet(DB)
    sql = """
    SELECT run_timestamp
    FROM
      runs
    WHERE
      run_id= ?
    """
    c = transaction(d.conn, sql, run_id)
    run_timestamp = one(c, 'run_timestamp')
    return run_timestamp


def timestamp_to_fmt(ts, fmt="%Y-%m-%d %H:%M:%S"):
    return time.strftime(fmt, time.gmtime(ts))