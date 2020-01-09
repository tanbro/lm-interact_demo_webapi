"""
Chat 的状态机
"""

import argparse
from copy import deepcopy
from dataclasses import dataclass
from typing import List, Optional

from transitions.extensions import (HierarchicalGraphMachine,
                                    HierarchicalMachine)
from transitions.extensions.nesting import NestedState

from ..models.chat import BaseMessage

NestedState.separator = '.'

PROMPT_STATEMACHINE = HierarchicalMachine(
    initial='ask',
    states=['yes', 'no'],
    transitions=[
        dict(trigger='prompt.result', source='ask', dest='yes', conditions=['is_yes']),
        dict(trigger='prompt.result', source='ask', dest='no'),
    ],
)

INITIAL = 'hi'

FINALS = ['bye', 'booked']

STATES = [
    INITIAL,
    dict(name='dialog', on_enter='inc_dialog_count'),
    dict(name='suggest', children=PROMPT_STATEMACHINE),
    'booked',
    'bye',
]

TRANSITIONS = [
    dict(trigger='text', source=INITIAL, dest='dialog'),
    dict(trigger='text', source='dialog', dest='suggest', conditions=['is_dialog_count_gt_zero']),
    dict(trigger='text', source='dialog', dest='dialog'),
    dict(trigger='', source='suggest.no', dest='bye'),
    dict(trigger='suggest.result', source='suggest.yes', dest='booked'),
]

KWARGS = dict(states=STATES, transitions=TRANSITIONS, initial=INITIAL)


@dataclass
class StateModel:
    dialog_count: int = 0
    history: Optional[List[BaseMessage]] = None

    def __post_init__(self):
        if not self.history:
            self.history = []

    def inc_dialog_count(self, val=1):
        self.dialog_count += val

    def is_dialog_count_gt_zero(self):
        return self.dialog_count > 0

    def is_yes(self, value):
        # pylint:disable=no-self-use
        return value.strip().lower() == 'yes'


def create_machine(model):
    return HierarchicalMachine(model=model, **KWARGS)


def main():
    parser = argparse.ArgumentParser(prog='CMD', description='输出 chat 的状态机图到文件')
    parser.add_argument('output_files', type=str, nargs='+', help='输出文件(*.dot, *.svg, *.png, *.jpg)')
    arguments = parser.parse_args()

    # draw the diagram
    kwargs = deepcopy(KWARGS)
    kwargs.update({
        'show_conditions': True,
        'show_state_attributes': True
    })
    machine = HierarchicalGraphMachine(**kwargs)
    for file_name in arguments.output_files:
        print(f'save state machine diagram to {file_name}')
        machine.get_graph(title='chat').draw(file_name, prog='dot')


if __name__ == "__main__":
    main()
