CREATE DATABASE CompatFlowSupplier;
GO
USE CompatFlowSupplier;
GO
CREATE TABLE dbo.SupplierProducts (
    sku NVARCHAR(64) NOT NULL PRIMARY KEY,
    title NVARCHAR(200) NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL,
    currency CHAR(3) NOT NULL,
    quantity INT NOT NULL
);
GO
INSERT INTO dbo.SupplierProducts (sku, title, unit_price, currency, quantity) VALUES
('SIM-SQL-001', 'Hydraulic Filter', 14.25, 'USD', 55),
('SIM-SQL-002', 'Pressure Gauge', 31.00, 'USD', 18);
GO
CREATE LOGIN compatflow_reader WITH PASSWORD = '__SIMULATOR_READER_PASSWORD__';
GO
USE CompatFlowSupplier;
GO
CREATE USER compatflow_reader FOR LOGIN compatflow_reader;
GRANT SELECT ON dbo.SupplierProducts TO compatflow_reader;
GO
