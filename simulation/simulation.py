import os
import math
from configparser import ConfigParser
from dateutil.relativedelta import relativedelta

import numpy as np
import pandas as pd
import eikon as ek
import xlwings as xw


def main():
    # Eikon
    conf = ConfigParser()
    conf.read(os.path.join(os.path.dirname(__file__), '..', 'eikon.conf'))
    ek.set_app_key(conf['eikon']['APP_KEY'])

    # Excel
    sheet = xw.Book.caller().sheets[0]
    sheet.range('O1').expand().clear_contents()
    instrument = sheet['E5'].value
    start_date = sheet['E4'].value
    end_date = start_date + relativedelta(years=2)

    # History
    prices = ek.get_timeseries(instrument,
                               fields='close',
                               start_date=start_date,
                               end_date=end_date)

    # Take mean and standard deviation from first 252 trading days
    trading_days = 252
    returns = np.log(prices[:trading_days] / prices[:trading_days].shift(1))
    mean = float(np.mean(returns) * trading_days)
    stdev = float(returns.std() * math.sqrt(trading_days))

    # Simulation parameters
    num_simulations = sheet.range('E3').options(numbers=int).value
    time = 1  # years
    num_timesteps = trading_days
    dt = time/num_timesteps  # Length of time period
    vol = stdev
    mu = mean  # Drift
    starting_price = float(prices.iloc[trading_days - 1])
    percentile_selection = [5, 50, 95]

    # Preallocation and intial values
    price = np.zeros((num_timesteps, num_simulations))
    percentiles = np.zeros((num_timesteps, 3))
    price[0, :] = starting_price
    percentiles[0, :] = starting_price

    # Simulation at each time step (log normal distribution)
    for t in range(1, num_timesteps):
        rand_nums = np.random.randn(num_simulations)
        price[t, :] = price[t-1, :] * np.exp((mu - 0.5 * vol**2) * dt + vol * rand_nums * np.sqrt(dt))
        percentiles[t, :] = np.percentile(price[t, :], percentile_selection)

    # Turn into pandas DataFrame
    index = pd.date_range(prices[:trading_days].index[-1], periods=trading_days, freq='B')
    simulation = pd.DataFrame(data=percentiles, index=index,
                              columns=['5th Percentile', 'Median', '95th Percentile'])

    # Concat history and simulation and reorder cols
    combined = pd.concat([prices, simulation], axis=1)
    combined = combined[['5th Percentile', 'Median', '95th Percentile', 'CLOSE']]
    sheet['O1'].value = combined
    sheet.charts['Chart 3'].set_source_data(sheet['O1'].expand())


if __name__ == '__main__':
    # This part is to run the script directly from Python, not via Excel
    xw.books.active.set_mock_caller()
    main()