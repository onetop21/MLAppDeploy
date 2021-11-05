import sys
import click

from click import command, option, Option, UsageError


class MutuallyExclusiveOption(Option):
    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
        help = kwargs.get('help', '')
        if self.mutually_exclusive:
            ex_str = ', '.join(self.mutually_exclusive)
            kwargs['help'] = help + (
                ' NOTE: This argument is mutually exclusive with '
                f' arguments: [{ex_str}].'
            )
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise UsageError(
                f'Illegal usage: `{self.name}` is mutually exclusive with '
                f'arguments `{",".join(self.mutually_exclusive)}`.'
            )

        return super().handle_parse_result(ctx, opts, args)
