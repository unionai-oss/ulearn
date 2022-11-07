"""Module to handle scheduling launchplans."""

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from functools import partial
from typing import Optional, Union

from flytekit import CronSchedule, FixedRate, LaunchPlan
from flytekit.core.workflow import WorkflowBase


class ScheduleType(Enum):
    trainer = "trainer"
    predictor = "predictor"


@dataclass
class Schedule:
    type: Union[str, ScheduleType]
    name: str
    expression: Optional[str] = None
    offset: Optional[str] = None
    fixed_rate: Optional[timedelta] = None
    time_arg: Optional[str] = None
    kwargs: Optional[dict] = None

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = ScheduleType[self.type]


def create_scheduled_launchplan(
    workflow: WorkflowBase,
    name: str,
    *,
    expression: Optional[str] = None,
    offset: Optional[str] = None,
    fixed_rate: Optional[timedelta] = None,
    time_arg: Optional[str] = None,
    **kwargs,
) -> LaunchPlan:
    """Create a :class:`~flytekit.LaunchPlan` with a schedule.

    :param workflow: UnionML-derived workflow.
    :param name: unique name of the launch plan
    :param expression: a cron expression (see
        `here <https://docs.flyte.org/en/latest/concepts/schedules.html#cron-expression>`__)
        or valid croniter schedule for e.g. `@daily`, `@hourly`, `@weekly`, `@yearly`
        (see `here <https://github.com/kiorky/croniter#keyword-expressions>`__).
    :param offset: duration to offset the schedule, must be a valid ISO 8601
        duration. Only used if ``expression`` is specified.
    :param fixed_rate: a :class:`~datetime.timedelta` object representing fixed
        rate with which to run the workflow.
    :param time_arg: the name of the argument in the ``workflow`` that will receive
        the kickoff time of the scheduled launchplan.
    :param kwargs: additional keyword arguments to pass to
        :class:`~flytekit.LaunchPlan`
    :returns: a scheduled launch plan object.
    """
    if expression is not None and fixed_rate is not None:
        raise ValueError("You must specify exactly one of 'expression' or 'fixed_rate', not both.")
    elif expression:
        schedule = CronSchedule(
            schedule=expression,
            offset=offset,
            kickoff_time_input_arg=time_arg,
        )
    elif fixed_rate:
        schedule = FixedRate(
            duration=fixed_rate,
            kickoff_time_input_arg=time_arg,
        )
    else:
        raise ValueError("You must specify exactly one of 'expression' or 'fixed_rate'.")
    return LaunchPlan.get_or_create(
        name=name,
        workflow=workflow,
        schedule=schedule,
        **kwargs,
    )


def schedule_trainer(
    fn=None,
    *,
    name: str,
    expression: Optional[str] = None,
    offset: Optional[str] = None,
    fixed_rate: Optional[timedelta] = None,
    reader_time_arg: Optional[str] = None,
    **kwargs,
):
    """Schedule the training service when the UnionML app is deployed.

    :param name: unique name of the schedule
    :param expression: a cron expression (see
        `here <https://docs.flyte.org/en/latest/concepts/schedules.html#cron-expression>`__)
        or valid croniter schedule for e.g. `@daily`, `@hourly`, `@weekly`, `@yearly`
        (see `here <https://github.com/kiorky/croniter#keyword-expressions>`__).
    :param offset: duration to offset the schedule, must be a valid
        `ISO 8601 duration <https://en.wikipedia.org/wiki/ISO_8601>__. Only
        used if ``expression`` is specified.
    :param fixed_rate: a :class:`~datetime.timedelta` object representing fixed
        rate with which to run the workflow.
    :param reader_time_arg: if not ``None``, the name of the
        :meth:`~unionml.dataset.Dataset.reader` argument that will receive
        the kickoff ``datetime`` of the scheduled launchplan.
    :param kwargs: additional keyword arguments to pass to
        :class:`~flytekit.LaunchPlan`
    """
    if hasattr(fn, "__unionml_trainer__"):
        raise ValueError("You must use @schedule_trainer below the @model.trainer decorator")

    if fn is None:
        return partial(
            schedule_trainer,
            name=name,
            expression=expression,
            offset=offset,
            fixed_rate=fixed_rate,
            reader_time_arg=reader_time_arg,
            **kwargs,
        )

    schedule = Schedule(ScheduleType.trainer, name, expression, offset, fixed_rate, reader_time_arg, kwargs)
    if hasattr(fn, "__unionml_model__"):
        from unionml import Model

        model: Model = fn.__unionml_model__
        model.add_training_schedule(schedule)
        return fn

    if hasattr(fn, "__unionml_schedules__"):
        fn.__unionml_schedules__.append(schedule)
    else:
        fn.__unionml_schedules__ = [schedule]
    return fn


def schedule_predictor(
    fn=None,
    *,
    name: str,
    expression: Optional[str] = None,
    offset: Optional[str] = None,
    fixed_rate: Optional[timedelta] = None,
    reader_time_arg: Optional[str] = None,
    **kwargs,
):
    """Schedule the prediction service when the UnionML app is deployed.

    :param name: unique name of the schedule
    :param expression: a cron expression (see
        `here <https://docs.flyte.org/en/latest/concepts/schedules.html#cron-expression>`__)
        or valid croniter schedule for e.g. `@hourly`, `@daily`, `@weekly`, `@monthly`, `@yearly`
        (see `here <https://github.com/kiorky/croniter#keyword-expressions>`__).
    :param offset: duration to offset the schedule, must be a valid
        `ISO 8601 duration <https://en.wikipedia.org/wiki/ISO_8601>__. Only
        used if ``expression`` is specified.
    :param fixed_rate: a :class:`~datetime.timedelta` object representing fixed
        rate with which to run the workflow.
    :param reader_time_arg: if not ``None``, the name of the
        :meth:`~unionml.dataset.Dataset.reader` argument that will receive
        the kickoff ``datetime`` of the scheduled launchplan.
    :param kwargs: additional keyword arguments to pass to
        :class:`~flytekit.LaunchPlan`
    """
    if hasattr(fn, "__unionml_predictor__"):
        raise ValueError("You must use @schedule_predictor below the @model.predictor decorator")

    if fn is None:
        return partial(
            schedule_predictor,
            name=name,
            expression=expression,
            offset=offset,
            fixed_rate=fixed_rate,
            reader_time_arg=reader_time_arg,
            **kwargs,
        )

    schedule = Schedule(ScheduleType.predictor, name, expression, offset, fixed_rate, reader_time_arg, kwargs)
    if hasattr(fn, "__unionml_model__"):
        from unionml import Model

        model: Model = fn.__unionml_model__
        model.add_prediction_schedule(schedule)

    if hasattr(fn, "__unionml_schedules__"):
        fn.__unionml_schedules__.append(schedule)
    else:
        fn.__unionml_schedules__ = [schedule]
    return fn