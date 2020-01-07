"""
状态机定义
"""

import argparse
from copy import deepcopy
from dataclasses import dataclass
from typing import List

from transitions import Machine
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
    dict(name='dialog', on_enter='inc_predict_count'),
    dict(name='suggest', children=PROMPT_STATEMACHINE),
    'booked',
    'bye',
]

TRANSITIONS = [
    dict(trigger='text', source=INITIAL, dest='dialog'),
    dict(trigger='text', source='dialog', dest='suggest', conditions=['is_to_suggest']),
    dict(trigger='text', source='dialog', dest='dialog'),
    dict(trigger='', source='suggest.no', dest='bye'),
    dict(trigger='suggest.result', source='suggest.yes', dest='booked'),
]

KWARGS = dict(states=STATES, transitions=TRANSITIONS, initial=INITIAL)


@dataclass
class StateModel:
    predict_count: int = 0
    history: List[BaseMessage] = None

    def __post_init__(self):
        if not self.history:
            self.history = []

    def inc_predict_count(self):
        self.predict_count += 1

    def is_to_suggest(self):
        # 如：已经进行了一次ML预测输出，就要推荐咨询师！
        if self.predict_count > 0:
            return True
        return False

    def is_yes(self, value):
        return value.strip().lower() == 'yes'


def create_machine(model):
    return HierarchicalMachine(model=model, **KWARGS)


def main():
    parser = argparse.ArgumentParser(description='生成状态机图')
    parser.add_argument('output_files', type=str, nargs='+', help='状态机图的输出文件')
    arguments = parser.parse_args()

    # draw the diagram
    kwargs = deepcopy(KWARGS)
    kwargs.update(dict(
        show_conditions=True, show_state_attributes=True
    ))
    machine = HierarchicalGraphMachine(**kwargs)
    for file_name in arguments.output_files:
        print(f'save state machine diagram to {file_name}')
        machine.get_graph(title='chat').draw(file_name, prog='dot')


if __name__ == "__main__":
    main()
