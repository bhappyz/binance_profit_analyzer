""" 
Author: Ahmad Dukhan
Github: https://github.com/bhappyz/
Twitter: https://twitter.com/dukhan
"""
import os
import threading
import time
from binance.client import Client
from datetime import datetime, timedelta
import dash
from dash import html, dcc
import dash_table
import pandas as pd
import plotly.graph_objects as go
import webbrowser
import PySimpleGUI as sg
import sys


class BinanceProfitChart:
    def __init__(self, api_key, api_secret, lookback_days):

        self.client = Client(api_key, api_secret)
        self.pairs = self.client.get_all_tickers()
        self.usdt_pairs = [pair for pair in self.pairs if pair['symbol'].endswith('USDT')]
        self.lookback_days = lookback_days
        self.use_percentage = False
        self.trades = {}
        self.profits = {}
        self.success_rates = {}
        self.oldest_trade_date = datetime.now()
        self.earliest_trade_date = datetime.now()

    def fetch_trades_with_progress(self, progress_bar, progress_window):
        total_pairs = len(self.usdt_pairs)
        for i, pair in enumerate(self.usdt_pairs, 1):
            symbol = pair['symbol']
            self.trades[symbol] = self.client.get_my_trades(symbol=symbol, limit=1000)
            time.sleep(1)  # Delay for 1 second
            progress_bar.Update(i, total_pairs)
            progress_window.refresh()


    def calculate_profit_loss(self):
        for symbol, trades_list in self.trades.items():
            # Exclude symbols with no trades in the specified lookback period
            if not trades_list:
                continue

            self.profits[symbol] = 0
            success_count = 0
            total_count = 0
            investment = 0
            oldest_trade_date = datetime.now()
            earliest_trade_date = datetime.now()

            for trade in trades_list:
                trade_date = datetime.fromtimestamp(trade['time'] / 1000)

                # Check if the trade is within the specified lookback period
                if trade_date < (datetime.now() - timedelta(days=self.lookback_days)):
                    continue

                if trade_date < oldest_trade_date:
                    oldest_trade_date = trade_date
                if trade_date > earliest_trade_date:
                    earliest_trade_date = trade_date

                if trade['isBuyer']:
                    # Store the buying quote value
                    investment = float(trade['quoteQty'])
                else:
                    # Compare selling quote value to buying quote value to determine success
                    selling_quote_value = float(trade['quoteQty'])
                    if investment > 0 and selling_quote_value > investment:
                        if self.use_percentage:
                            self.profits[symbol] += 100 * (selling_quote_value - investment) / investment
                        else:
                            self.profits[symbol] += selling_quote_value - investment
                        success_count += 1
                    else:
                        if self.use_percentage:
                            self.profits[symbol] -= 100 * (investment - selling_quote_value) / investment
                        else:
                            self.profits[symbol] -= investment - selling_quote_value
                    total_count += 1

            if total_count > 0:
                self.success_rates[symbol] = success_count / total_count
                self.oldest_trade_date = min(self.oldest_trade_date, oldest_trade_date)
                self.earliest_trade_date = max(self.earliest_trade_date, earliest_trade_date)

    def create_chart(self):
        # Sort symbols based on profits in descending order
        sorted_symbols = sorted(self.profits.keys(), key=lambda x: self.profits[x], reverse=True)

        # Extract profits and success rates for sorted symbols
        sorted_profits = [self.profits[symbol] for symbol in sorted_symbols]
        sorted_success_rates = [self.success_rates.get(symbol, 0) for symbol in sorted_symbols]

        # Create a table of symbol, profit/loss, success rate, and percentage profitable
        table_data = []
        for symbol in sorted_symbols:
            success_rate = self.success_rates.get(symbol, 0)
            profitable_percentage = f"{success_rate * 100:.2f}%"
            table_data.append(
                {
                    'Symbol': symbol,
                    'Profit/Loss': f"${self.profits[symbol]:.2f}",
                    'Success Rate': f"{success_rate:.2f}%",
                    'Percentage Profitable': profitable_percentage,
                }
            )

        # Create a pandas DataFrame from the table data
        df = pd.DataFrame(table_data)

        # Create the bar chart for the table
        bar_fig = go.Figure(data=[
            go.Bar(x=df['Symbol'], y=df['Profit/Loss'], name='Profit/Loss'),
            go.Bar(x=df['Symbol'], y=df['Success Rate'], name='Success Rate')
        ])
        bar_fig.update_layout(
            title='Profit/Loss and Success Rate for All Symbols',
            xaxis_title='Symbol',
            yaxis_title='Value',
            barmode='group'
        )

        # Create the table component with sortable columns
        table = dash_table.DataTable(
            id='table',
            columns=[{"name": col, "id": col} for col in df.columns],
            data=df.to_dict('records'),
            sort_action='native',
            sort_mode='multi',
            style_table={'overflowX': 'auto'},
            style_cell={'textAlign': 'left'},
        )

        # Initialize the Flask application
        app = dash.Dash(__name__)

        # Create the layout for the Flask application
        app.layout = html.Div([
            html.H1("Binance Profit Chart"),
            dcc.Graph(figure=bar_fig),
            html.H3("Table of Symbol Data"),
            table
        ])

        # Define the Flask server
        server = app.server

        # Start a new thread to run the Flask application
        def run_flask_app():
            app.run_server()

        flask_thread = threading.Thread(target=run_flask_app)
        flask_thread.start()

        # Open the web browser after a short delay to allow the Flask application to start
        time.sleep(2)
        webbrowser.open("http://localhost:8050")
        time.sleep(5)

        # Kill the app
        os._exit(0)
        # Join the Flask thread to wait for it to finish
        flask_thread.join()

class BinanceProfitChartGUI:
    def __init__(self):
        self.api_key = None
        self.api_secret = None
        self.lookback_days = None

    def run(self):
        # Define the GUI layout

        layout = [
            [sg.Text('API Key:'), sg.Input(key='-API-KEY-')],
            [sg.Text('API Secret:'), sg.Input(key='-API-SECRET-', password_char='*')],
            [sg.Text('Days to Look Back:'), sg.Input(key='-LOOKBACK-DAYS-', justification='right')],
            [sg.Button('Run'), sg.Button('Exit')],
            # make hight 300
        ]

        # Create the window
        window = sg.Window('Binance Profit Chart', layout)

        # Event loop
        while True:
            event, values = window.read()

            if event == sg.WINDOW_CLOSED or event == 'Exit':
                break

            if event == 'Run':
                self.api_key = values['-API-KEY-']
                self.api_secret = values['-API-SECRET-']
                self.lookback_days = values['-LOOKBACK-DAYS-']

                if not self.api_key or not self.api_secret or not self.lookback_days:
                    sg.popup('Please fill in all the fields.', title='Error')
                elif not self.lookback_days.isdigit():
                    sg.popup('Invalid input for Days to Look Back. Please enter a valid number.', title='Error')
                else:
                    window.Hide()
                    self.run_binance_profit_chart()

        # Close the window
        window.close()

    def run_binance_profit_chart(self):
        try:
            chart = BinanceProfitChart(self.api_key, self.api_secret, int(self.lookback_days))
            layout = [
                [sg.Text('Fetching trades...')],
                [sg.ProgressBar(100, orientation='h', size=(30, 20), key='-PROGRESS-BAR-')]
            ]
            progress_window = sg.Window('Progress', layout, finalize=True)
            progress_bar = progress_window['-PROGRESS-BAR-']

            # Call fetch_trades_with_progress directly
            chart.fetch_trades_with_progress(progress_bar, progress_window)

            # Calculate profit/loss
            chart.calculate_profit_loss()

            # Create chart
            chart.create_chart()

            # Close progress bar window
            progress_window.close()

            # Open the web page in a browser
            webbrowser.open("http://localhost:8050")

            # Sleep for a few seconds to allow the page to load
            time.sleep(5)

            # Kill the app
            os._exit(0)
        except Exception as e:
            sg.popup(f'Error occurred: {str(e)}', title='Error')
            sys.exit(1)

if __name__ == '__main__':
    gui = BinanceProfitChartGUI()

    # Run the GUI
    gui.run()
