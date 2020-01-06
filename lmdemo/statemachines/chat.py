"""
状态机定义
"""

import argparse
from typing import Any, Dict, List, Tuple, Union

from transitions import Machine
from transitions.extensions import (HierarchicalGraphMachine,
                                    HierarchicalMachine)
from transitions.extensions.nesting import NestedState


NestedState.separator = '.'


SUGGEST_STATEMACHINE = HierarchicalMachine(
    initial='asking',
    states=['asking', 'agreed'],
    transitions=[
        ['agree', 'asking', 'agreed'],
    ],
)


INITIAL = 'hi'

STATES = [
    INITIAL,
    'dialog',
    dict(name='suggest', children=SUGGEST_STATEMACHINE),
    'booked',
    'bye',
]


TRANSITIONS = [
    dict(trigger='text_message', source=INITIAL, dest='dialog'),
    dict(trigger='text_message', source='dialog', dest='suggest', conditions=['is_to_suggest']),
    dict(trigger='text_message', source='dialog', dest='dialog'),
    dict(trigger='disagree', source='suggest.asking', dest='bye'),
    dict(trigger='book', source='suggest.agreed', dest='booked'),
]


MACHINE_KWARGS = dict(states=STATES, transitions=TRANSITIONS, initial=INITIAL)


def create_machine(model):
    return HierarchicalMachine(model=model, **MACHINE_KWARGS)


def main():
    parser = argparse.ArgumentParser(description='生成状态机图')
    parser.add_argument('output_files', type=str, nargs='+', help='状态机图的输出文件')
    arguments = parser.parse_args()

    # draw the diagram
    machine = HierarchicalGraphMachine(show_conditions=True, **MACHINE_KWARGS)
    for file_name in arguments.output_files:
        print(f'save state machine diagram to {file_name}')
        machine.get_graph().draw(file_name, prog='dot')


if __name__ == "__main__":
    main()
