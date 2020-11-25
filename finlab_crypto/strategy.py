"""Strategy function plug-in.

You can use Filter and Strategy function as decorator
that make strategies easy to construct filters layers
and common strategy detection methods, such as back-testing,
parameter tuning and analysis charts.

  Typical usage example:

  @Filter(timeperiod=20)
  def your_filter(ohlcv):
      your filter logic...
      return filter > filter value, figures
  f60 = your_filter.create({'timeperiod': 60})

  -------------------------------

  @Strategy()
  def your_strategy(ohlcv):
     your strategy logic...
      return entries, exits, figures
  portfolio = your_strategy.backtest(ohlcv, freq='4h', plot=True)

"""

from finlab_crypto.utility import (enumerate_variables, enumerate_signal,
                                   stop_early, plot_combination, plot_strategy,
                                   variable_visualization, remove_pd_object
                                  )
from finlab_crypto.overfitting import CSCV
import copy
import vectorbt as vbt
import pandas as pd
import matplotlib.pyplot as plt
from collections.abc import Iterable


def Filter(**default_parameters):
    """As decorator layer.
    Let customized filter functions have class Filter features.

    Args:
      **default_parameters:
        your customized filter functions args default value.

    Returns:
      decorator inner function.
    """
    class Filter:
        """Filter package features plug-in.

        Offer easy way to create filter to use in class Strategy.

        Attributes:
            func: A function that is your customized filter.
            _variables: A dict of your customized filter attributes.
            filters:A dict of your customized filters attributes.

        """

        def __init__(self, func,):
            """Inits Filter."""
            self.func = func
            self._variables = None
            self.filters = {}
            self.set_parameters(default_parameters)

        def set_parameters(self, variables):
            """Set your customized filter parameters.

            Let Filter class use variables dict to set method

            Args::
              variables:
                A dict of your customized filter attributes.

            """
            if variables:
                for key, val in variables.items():
                    setattr(self, key, val)
            self._variables = variables

        def show_parameters(self):
            print(self._variables)

        def create(self, variables=None):
            """Generate filter signals, fig_data.

            Offer easy way to create filter signals, fig_data

            Args:
              variables:
                A dict of your customized filter attributes.
            Returns:
              signals:
                A dataframe of filter signals.
              fig_data:
                A dict of required data for figure display.
            """
            def ret_f(ohlcv):

                variable_enumerate = enumerate_variables(variables)
                if len(variable_enumerate) == 0:
                    variable_enumerate.append(default_parameters)

                signals = {}
                fig_data = {}
                for v in variable_enumerate:

                    self.set_parameters(v)
                    results = self.func(ohlcv)

                    v = remove_pd_object(v)

                    if isinstance(results, Iterable):
                        signals[str(v)], fig_data = results
                    else:
                        signals[str(v)] = results

                signals = pd.DataFrame(signals)
                signals.columns.name = 'filter'

                param_names = list(eval(signals.columns[0]).keys())
                arrays = ([signals.columns.map(lambda s: eval(s)[p]) for p in param_names])
                tuples = list(zip(*arrays))
                columns = pd.MultiIndex.from_tuples(tuples, names=param_names)
                signals.columns = columns

                return signals, fig_data

            return ret_f

    def deco(func):
        """Decorator inner function.

        Args:
          func:
            your customized filter.

        Returns:
            A class of Filter(func).
        """
        return Filter(func)

    return deco

def Strategy(**default_parameters):
    """As decorator layer.
    Let customized strategy functions have class Strategy features.

    Args:
      **default_parameters: your customized strategy functions args default value.

    Returns:
      decorator inner function.
    """
    class Strategy:
        """Strategy features plug-in.

        Offer common strategy detection methods, such as back-testing,
        parameter tuning and analysis charts.

        Attributes:
            func: A function that is your customized strategy.
            _variables: A dict of your customized strategy attributes.
            filters:A dict of your customized filters attributes.

        """

        def __init__(self, func):
            """Inits Strategy."""
            self.func = func
            self._variables = None
            self.filters = {}
            self.set_parameters(default_parameters)

        def set_parameters(self, variables):
            """Set your customized strategy parameters.

            Let Strategy class use variables dict to set method.

            Args::
              variables:
                A dict of your customized strategy attributes.

            """
            if variables:
                for key, val in variables.items():
                    setattr(self, key, val)
            self._variables = variables

        def show_parameters(self):
            print(self._variables)

        @staticmethod
        def _enumerate_filters(ohlcv, filters):
            """Enumerate filters data.

            Process filter dictionary data to prepare for adding filter signals.

            Args:
              ohlcv:
                A dataframe of your trading target.
              filters:
                A dict of your customized filter Attributes.

            Returns:
              A dict that generate tuple with filter signal dataframe and figures data.
              For example:

            {'mmi': (timeperiod                    20
              timestamp
              2020-11-25 02:00:00+00:00   True
              2020-11-25 03:00:00+00:00   True
              2020-11-25 04:00:00+00:00   True

              [3 rows x 1 columns], {'figures': {'mmi_index': timestamp
                2020-11-25 02:00:00+00:00    0.7
                2020-11-25 03:00:00+00:00    0.7
                2020-11-25 04:00:00+00:00    0.7
                Name: close, Length: 28597, dtype: float64}})}

            """
            ret = {}
            for fname, f in filters.items():

                # get filter signals and figures
                filter_df, filter_figures = f(ohlcv)
                ret[fname] = (filter_df, filter_figures)
            return ret

        @staticmethod
        def _add_filters(entries, exits, fig_data, filters):
            """Add filters in strategy.

            Generate entries, exits, fig_data after add filters.

            Args:
              entries:
                A dataframe of entries point time series.
              exits:
                A dataframe of exits point time series.
              fig_data:
                A dict of your customized figure Attributes.
              filters:
                A dict of _enumerate_filters function return.

            Returns:
              entries:
                A dataframe of entries point time series after add filter function.
              exits:
                A dataframe of exits point time series after add filter function.
              fig_data
                A dict of tuple with filter signal dataframe and figures data.

            """
            for fname, (filter_df, filter_figures) in filters.items():
                filter_df.columns = filter_df.columns.set_names([fname + '_' + n for n in filter_df.columns.names])
                entries = filter_df.vbt.tile(entries.shape[1]).vbt & entries.vbt.repeat(filter_df.shape[1]).vbt
                exits = exits.vbt.repeat(filter_df.shape[1])
                exits.columns = entries.columns

                # merge figures
                if filter_figures is not None:
                    if 'figures' in filter_figures:
                        if 'figures' not in fig_data:
                            fig_data['figures'] = {}
                        for name, fig in filter_figures['figures'].items():
                            fig_data['figures'][fname+'_'+name] = fig
                    if 'overlaps' in filter_figures:
                        if 'overlaps' not in fig_data:
                            fig_data['overlaps'] = {}
                        for name, fig in filter_figures['overlaps'].items():
                            fig_data['overlaps'][fname+'_'+name] = fig

            return entries, exits, fig_data

        @staticmethod
        def _add_stops(ohlcv, entries, exits, variables):
            """Add early trading stop condition in strategy.

            Args:
              ohlcv:
                A dataframe of your trading target.
              entries:
                A dataframe of entry point time series.
              exits:
                A dataframe of exits point time series.
              variables:
                A dict of your customized strategy Attributes.

            Returns:
              entries:
                A dataframe of entries point time series after add stop_early function.
              exits:
                A dataframe of exits point time series after add stop_early function.

            """
            entries, exits = stop_early(ohlcv, entries, exits, variables)
            entries = entries.squeeze()
            exits = exits.squeeze()
            return entries, exits

        def backtest(self, ohlcv, variables=dict(),
                filters=dict(), lookback=None, plot=False,
                signals=False, side='long', cscv_nbins=10, 
                cscv_objective=lambda r:r.mean(), html=None, **args):

            """Backtest analysis tool set.
            Use vectorbt as base module to create numerical operations features.
            Use seaborn and pyechart as base modules to create analysis charts platform.

            Args:
              ohlcv:
                Required.
                A dataframe of your trading target.
              variables:
                A dict of your customized strategy Attributes.
                Default is empty dict.
              filters:
                A dict of your customized filter Attributes.
                Default is empty dict.
              lookback:
                A int of slice that you want to get recent ohlcv.
                Default is None.
              plot:
                A bool of control plot display.
                Default is False.
              signals:
                A bool of controlentries, exits, fig_data return.
                Default is False.
              side:
                A str of transaction direction,short or long.
                Default is long.
              cscv_nbins:
                A int of CSCV algorithm bin size to control overfitting calculation.
                Default is 10.
              cscv_objective:
                A function of CSCV algorithms objective.
                Default is lambda r:r.mean().
              html:
                A str of your customized html format file to show plot.
                Default is None.
              **args:
                Other parameters.

            Returns:
                A dataframe of vectorbt.Portfolio.from_signals results
                Plot results display.

            Raises:
                'Shorting is not support yet':if side is 'short'.
                "side should be 'long' or 'short'":if side is not 'short' or 'long'.

            """
            variables_without_stop = copy.copy(variables)

            exit_vars = ['sl_stop', 'ts_stop', 'tp_stop']
            stop_vars = {}
            for e in exit_vars:
                if e in variables_without_stop:
                    stop_vars[e] = variables[e]
                    variables_without_stop.pop(e)

            ohlcv_lookback = ohlcv.iloc[-lookback:] if lookback else ohlcv

            variable_enumerate = enumerate_variables(variables_without_stop)

            if not variable_enumerate:
                variable_enumerate = [default_parameters]

            entries, exits, fig_data = enumerate_signal(ohlcv_lookback, self, variable_enumerate)

            if filters:
                filter_signals = self._enumerate_filters(ohlcv_lookback, filters)
                entries, exits, fig_data = self._add_filters(entries, exits, fig_data, filter_signals)

            entries, exits = self._add_stops(ohlcv_lookback, entries, exits, stop_vars)

            if signals:
                return entries, exits, fig_data

            if side == 'long':
                portfolio = vbt.Portfolio.from_signals(
                    ohlcv_lookback.close, entries.fillna(False), exits.fillna(False), **args)

            elif side == 'short':
                raise Exception('Shorting is not support yet')

            else:
                raise Exception("side should be 'long' or 'short'")

            if (plot or html is not None) and isinstance(entries, pd.Series):
                plot_strategy(ohlcv_lookback, entries, exits, portfolio ,fig_data, html=html)

            elif plot and isinstance(entries, pd.DataFrame):

                # perform CSCV algorithm
                cscv = CSCV(n_bins=cscv_nbins, objective=cscv_objective)
                cscv.add_daily_returns(portfolio.daily_returns())
                cscv_result = cscv.estimate_overfitting(plot=False)

                # plot results
                plot_combination(portfolio, cscv_result)
                plt.show()
                variable_visualization(portfolio)

            return portfolio


    def deco(func):
        """Decorator inner function.

        Args:
          func:
            your customized strategy.

        Returns:
            A class of Strategy(func)
        """
        return Strategy(func)

    return deco
