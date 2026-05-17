-- ======================================================
-- 115年度公文管理系統 - 基礎對照表 (Ref Tables) 初始化腳本
-- 功能：清空舊表、重建結構、寫入正規化對照資料
-- ======================================================

-- 暫時關閉外鍵約束檢查，避免重建表時發生報錯
PRAGMA foreign_keys = OFF;

-- ------------------------------------------------------
-- 1. 刑事案件狀態 (Ref_Case_Status)
-- ------------------------------------------------------
DROP TABLE IF EXISTS Ref_Case_Status;
CREATE TABLE Ref_Case_Status (
    gen_cat_id   VARCHAR(10) PRIMARY KEY,
    gen_cat_name VARCHAR(50) NOT NULL
);

INSERT INTO Ref_Case_Status (gen_cat_id, gen_cat_name) VALUES 
('CS01', 'A_現行犯'),
('CS02', 'B_到案'),
('CS03', 'B_未到案');

-- ------------------------------------------------------
-- 2. 一般陳報分類 (Ref_General_Category)
-- ------------------------------------------------------
DROP TABLE IF EXISTS Ref_General_Category;
CREATE TABLE Ref_General_Category (
    gen_cat_id   VARCHAR(10) PRIMARY KEY,
    gen_cat_name VARCHAR(50) NOT NULL
);

INSERT INTO Ref_General_Category (gen_cat_id, gen_cat_name) VALUES 
('GC01', 'D_業務陳報'),
('GC02', 'F_司法相驗'),
('GC03', 'J_其他');

-- ------------------------------------------------------
-- 3. 單位名單 (Ref_Departments)
-- ------------------------------------------------------
DROP TABLE IF EXISTS Ref_Departments;
CREATE TABLE Ref_Departments (
    dept_id   VARCHAR(10) PRIMARY KEY,
    dept_name VARCHAR(50) NOT NULL
);

INSERT INTO Ref_Departments (dept_id, dept_name) VALUES 
('D01', '交通組'),
('D02', '偵查隊'),
('D03', '防治組'),
('D04', '行政組'),
('D05', '督察組'),
('D06', '人事室'),
('D07', '保民組'),
('D08', '保防組'),
('D09', '秘書室'),
('D10', '會計室'),
('D11', '勤指中心');

-- ------------------------------------------------------
-- 4. 人員名單 (Ref_Personnel)
-- ------------------------------------------------------
DROP TABLE IF EXISTS Ref_Personnel;
CREATE TABLE Ref_Personnel (
    staff_id   VARCHAR(10) PRIMARY KEY,
    staff_name VARCHAR(50) NOT NULL
);

INSERT INTO Ref_Personnel (staff_id, staff_name) VALUES 
('P01', '賴柏仁'),
('P02', '覃筱蘭'),
('P03', '游智程'),
('P04', '洪渝勛-01.10'),
('P05', '劉志廷-02'),
('P06', '徐維陽-04'),
('P07', '陳凱霖-05'),
('P08', '郭彥麟-07.22'),
('P09', '陳力豪-08'),
('P10', '劉星緯-09'),
('P11', '鄭郁勳-11'),
('P12', '楊詠翔-12'),
('P13', '謝欣蓉-13'),
('P14', '鄧敬豪-14'),
('P15', '邱垂政-15'),
('P16', '洪哲文-16'),
('P17', '嘺俊甫-17'),
('P18', '陳正道-18'),
('P19', '溫學成-19.06'),
('P20', '劉致忻-20.3'),
('P21', '古浩成-21'),
('P22', '秦志如-23'),
('P23', '林柏宏-24'),
('P24', '簡雄雄-25'),
('P25', '莊守翔-26'),
('P26', '馬瑞興-27'),
('P27', '呂紹榮-28'),
('P28', '黃柏嘉-29'),
('P29', '陳冠宇-30'),
('P30', '謝煥春-31'),
('P31', '胡展維-32'),
('P32', '林思維'),
('P33', '羅以芯'),
('P34', '游琇媛');

-- 重新開啟外鍵約束檢查
PRAGMA foreign_keys = ON;