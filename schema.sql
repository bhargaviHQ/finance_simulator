-- Create database
CREATE DATABASE IF NOT EXISTS stock_data;
USE stock_data;

-- Stocks table
CREATE TABLE IF NOT EXISTS stocks (
    cik VARCHAR(10) PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    exchange VARCHAR(50),
    UNIQUE(symbol)
);

-- Income statements table
CREATE TABLE IF NOT EXISTS income_statements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cik VARCHAR(10) NOT NULL,
    fiscal_date_ending DATE NOT NULL,
    revenue DECIMAL(20,2),
    net_income DECIMAL(20,2),
    FOREIGN KEY (cik) REFERENCES stocks(cik),
    UNIQUE(cik, fiscal_date_ending)
);

-- Balance sheets table
CREATE TABLE IF NOT EXISTS balance_sheets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cik VARCHAR(10) NOT NULL,
    fiscal_date_ending DATE NOT NULL,
    total_assets DECIMAL(20,2),
    total_liabilities DECIMAL(20,2),
    total_equity DECIMAL(20,2),
    FOREIGN KEY (cik) REFERENCES stocks(cik),
    UNIQUE(cik, fiscal_date_ending)
);

-- Cash flows table
CREATE TABLE IF NOT EXISTS cash_flows (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cik VARCHAR(10) NOT NULL,
    fiscal_date_ending DATE NOT NULL,
    operating_cash_flow DECIMAL(20,2),
    capital_expenditure DECIMAL(20,2),
    FOREIGN KEY (cik) REFERENCES stocks(cik),
    UNIQUE(cik, fiscal_date_ending)
);

-- Sample data
INSERT INTO stocks (cik, symbol, company_name, exchange) VALUES
('0000320193', 'AAPL', 'Apple Inc.', 'NASDAQ'),
('0001018724', 'AMZN', 'Amazon.com, Inc.', 'NASDAQ'),
('0001652044', 'GOOGL', 'Alphabet Inc.', 'NASDAQ');

INSERT INTO income_statements (cik, fiscal_date_ending, revenue, net_income) VALUES
('0000320193', '2024-09-30', 394328000000.00, 94760000000.00),
('0001018724', '2024-12-31', 574785000000.00, 30425000000.00),
('0001652044', '2024-12-31', 307394000000.00, 73795000000.00);

INSERT INTO balance_sheets (cik, fiscal_date_ending, total_assets, total_liabilities, total_equity) VALUES
('0000320193', '2024-09-30', 411976000000.00, 290437000000.00, 121539000000.00),
('0001018724', '2024-12-31', 527854000000.00, 325979000000.00, 201875000000.00),
('0001652044', '2024-12-31', 402392000000.00, 123509000000.00, 278883000000.00);

INSERT INTO cash_flows (cik, fiscal_date_ending, operating_cash_flow, capital_expenditure) VALUES
('0000320193', '2024-09-30', 122151000000.00, -10429000000.00),
('0001018724', '2024-12-31', 75747000000.00, -48805000000.00),
('0001652044', '2024-12-31', 101490000000.00, -31142000000.00);