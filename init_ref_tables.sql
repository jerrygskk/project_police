-- ======================================================
-- 115年度公文管理系統 - 完整初始化腳本 (含狀態判斷 View)
-- ======================================================

PRAGMA foreign_keys = OFF;

-- 1. 刪除舊有視圖與資料表
DROP VIEW IF EXISTS View_Task_Full;
DROP VIEW IF EXISTS View_Criminal_Full;
DROP VIEW IF EXISTS View_General_Full;

DROP TABLE IF EXISTS Document_Task;
DROP TABLE IF EXISTS Document_Criminal;
DROP TABLE IF EXISTS Document_General;
DROP TABLE IF EXISTS Ref_Personnel;
DROP TABLE IF EXISTS Ref_Departments;
DROP TABLE IF EXISTS Ref_Case_Status;
DROP TABLE IF EXISTS Ref_General_Category;
DROP TABLE IF EXISTS Ref_CaseTypes;

-- 2. 建立對照表
CREATE TABLE Ref_Departments (dept_id VARCHAR(10) PRIMARY KEY, dept_name VARCHAR(50) NOT NULL);
INSERT INTO Ref_Departments VALUES ('D01','交通組'),('D02','偵查隊'),('D03','防治組'),('D04','行政組'),('D05','督察組'),('D06','人事室'),('D07','保民組'),('D08','保防組'),('D09','秘書室'),('D10','會計室'),('D11','勤指中心');

CREATE TABLE Ref_Personnel (staff_id VARCHAR(10) PRIMARY KEY, staff_name VARCHAR(50) NOT NULL, is_active BOOLEAN NOT NULL DEFAULT 1);
INSERT INTO Ref_Personnel (staff_id, staff_name, is_active) VALUES 
('P01','賴柏仁',1),('P02','覃筱蘭',1),('P03','游智程',1),('P04','洪渝勛-01.10',1),('P05','劉志廷-02',1),('P06','徐維陽-04',1),('P07','陳凱霖-05',1),('P08','郭彥麟-07.22',1),('P09','陳力豪-08',1),('P10','劉星緯-09',1),('P11','鄭郁勳-11',1),('P12','楊詠翔-12',1),('P13','謝欣蓉-13',1),('P14','鄧敬豪-14',1),('P15','邱垂政-15',1),('P16','洪哲文-16',1),('P17','嘺俊甫-17',1),('P18','陳正道-18',1),('P19','溫學成-19.06',1),('P20','劉致忻-20.3',1),('P21','古浩成-21',1),('P22','秦志如-23',1),('P23','林柏宏-24',1),('P24','簡雄雄-25',1),('P25','莊守翔-26',1),('P26','馬瑞興-27',1),('P27','呂紹榮-28',1),('P28','黃柏嘉-29',1),('P29','陳冠宇-30',1),('P30','謝煥春-31',1),('P31','胡展維-32',1),('P32','林思維',1),('P33','羅以芯',1),('P34','游琇媛',1);

CREATE TABLE Ref_Case_Status (status_id VARCHAR(10) PRIMARY KEY, status_name VARCHAR(50) NOT NULL);
INSERT INTO Ref_Case_Status VALUES ('CS01','A_現行犯'),('CS02','B_到案'),('CS03','B_未到案');

CREATE TABLE Ref_General_Category (gen_cat_id VARCHAR(10) PRIMARY KEY, gen_cat_name VARCHAR(50) NOT NULL);
INSERT INTO Ref_General_Category VALUES ('GC01','D_業務陳報'),('GC02','F_司法相驗'),('GC03','J_其他');

CREATE TABLE Ref_CaseTypes (case_type_id VARCHAR(10) PRIMARY KEY, case_type_name VARCHAR(100) NOT NULL);
INSERT INTO Ref_CaseTypes VALUES ('CT01','通緝'),('CT02','毒品危害防制條例'),('CT03','185-3公共危險(酒)'),('CT04','185-3公共危險(毒)'),('CT05','320竊盜'),('CT06','321加重竊盜'),('CT07','339詐欺'),('CT08','失聯移工'),('CT09','135妨害公務'),('CT10','149聚眾不解散'),('CT11','150聚眾鬥毆'),('CT12','151恐嚇公眾'),('CT13','169-171誣告'),('CT14','185-4肇事逃逸'),('CT15','210-220偽造文書印文罪'),('CT16','235妨害風化'),('CT17','266-270賭博罪'),('CT18','271殺人'),('CT19','277傷害'),('CT20','284過失傷害'),('CT21','302妨害自由(私行拘禁)'),('CT22','304強制罪'),('CT23','305恐嚇危安'),('CT24','306侵入住宅'),('CT25','309-314妨害名譽及信用罪(公然侮辱、誹謗)'),('CT26','315-319妨害秘密罪'),('CT27','319-1到319-6妨害性隱私及不實性影像罪章'),('CT28','325準強盜'),('CT29','326搶奪'),('CT30','328強盜'),('CT31','330加重強盜'),('CT32','335侵占'),('CT33','342背信'),('CT34','344重利'),('CT35','346恐嚇取財'),('CT36','354毀損'),('CT37','358妨害電腦使用'),('CT38','★★刑案類找不到法條(暫選)'),('CT39','汽機車失竊'),('CT40','汽機車遺失/侵占'),('CT41','汽機車車牌遺失/侵占'),('CT42','其他汽機車案類'),('CT43','社會秩序維護法'),('CT44','家庭暴力防治法'),('CT45','個人資料保護法'),('CT46','跟蹤騷擾防治法'),('CT47','性騷擾防治法'),('CT48','菸害防制法'),('CT49','醫療法'),('CT50','人口販運防治法'),('CT51','農田水利法'),('CT52','廢棄物清理法');

-- 3. 建立主表
CREATE TABLE Document_Task (
    doc_id VARCHAR(50) PRIMARY KEY,
    receive_date DATE,
    receive_id VARCHAR(10),
    dept_id VARCHAR(10),
    subject TEXT,
    processor_id VARCHAR(10),
    deadline DATE,
    dispatch_date DATE,
    sender_id VARCHAR(10),
    timestamp DATETIME
);

CREATE TABLE Document_Criminal (
    doc_id VARCHAR(50) PRIMARY KEY, report_date DATE, sender_id VARCHAR(10), case_type VARCHAR(10), case_status VARCHAR(10), processor_id VARCHAR(10), subject_summary TEXT, occurrence_date DATE, reporter_name VARCHAR(50), receiver_id VARCHAR(10), is_reported BOOLEAN, is_electronic BOOLEAN
);

CREATE TABLE Document_General (
    doc_id VARCHAR(50) PRIMARY KEY, report_date DATE, sender_id VARCHAR(10), dept_id VARCHAR(10), gen_cat_id VARCHAR(10), subject TEXT, processor_id VARCHAR(10), is_reported BOOLEAN, is_electronic BOOLEAN
);

-- 4. 建立 Task 視圖 (含「剩餘天數/狀態」邏輯判斷)
CREATE VIEW View_Task_Full AS
SELECT 
    T.doc_id AS '編號', 
    T.receive_date AS '收文日期', 
    P2.staff_name AS '收文人員',
    D.dept_name AS '業務組', 
    T.subject AS '交辦事由', 
    P3.staff_name AS '所承辦人', 
    T.deadline AS '限辦日期',
    T.dispatch_date AS '發文日期', 
    P1.staff_name AS '送文人員',
    T.timestamp AS '紀錄時間',
    -- 核心條件判斷
    CASE 
        -- 1. 目前日期 < 限辦日期 且 發文日期不存在
        WHEN date('now', 'localtime') < T.deadline AND (T.dispatch_date IS NULL OR T.dispatch_date = '')
            THEN '剩餘 ' || CAST(julianday(T.deadline) - julianday(date('now', 'localtime')) AS INT) || ' 天'
        
        -- 2. 目前日期 = 限辦日期 且 發文日期不存在
        WHEN date('now', 'localtime') = T.deadline AND (T.dispatch_date IS NULL OR T.dispatch_date = '')
            THEN '本日截止'
        
        -- 3. 目前日期 > 限辦日期
        WHEN date('now', 'localtime') > T.deadline THEN
            CASE 
                -- 3a. 發文日期存在 且 小於限辦日期
                WHEN (T.dispatch_date IS NOT NULL AND T.dispatch_date <> '') AND T.dispatch_date <= T.deadline 
                    THEN '已發文'
                
                -- 3b. 發文日期存在 且 大於限辦日期
                WHEN (T.dispatch_date IS NOT NULL AND T.dispatch_date <> '') AND T.dispatch_date > T.deadline 
                    THEN '已發文，逾期 ' || CAST(julianday(T.dispatch_date) - julianday(T.deadline) AS INT) || ' 天'
                
                -- 3c. 發文日期不存在
                ELSE '逾期 ' || CAST(julianday(date('now', 'localtime')) - julianday(T.deadline) AS INT) || ' 天'
            END
        ELSE '' 
    END AS '狀態'
FROM Document_Task T
LEFT JOIN Ref_Personnel P1 ON T.sender_id = P1.staff_id
LEFT JOIN Ref_Personnel P2 ON T.receive_id = P2.staff_id
LEFT JOIN Ref_Personnel P3 ON T.processor_id = P3.staff_id
LEFT JOIN Ref_Departments D ON T.dept_id = D.dept_id;

-- 其他 View 保持不變
CREATE VIEW View_Criminal_Full AS SELECT C.doc_id AS '送文編號', C.report_date AS '陳報日期', P1.staff_name AS '送文人員', CT.case_type_name AS '案類', CS.status_name AS '發文分類', P2.staff_name AS '主承辦人', C.subject_summary AS '嫌疑人_案由', C.occurrence_date AS '受理日期', C.reporter_name AS '報案人', P3.staff_name AS '受理人', CASE WHEN C.is_reported = 1 THEN '是' ELSE '否' END AS '紙本', CASE WHEN C.is_electronic = 1 THEN '是' ELSE '否' END AS '電子檔' FROM Document_Criminal C LEFT JOIN Ref_Personnel P1 ON C.sender_id = P1.staff_id LEFT JOIN Ref_Personnel P2 ON C.processor_id = P2.staff_id LEFT JOIN Ref_Personnel P3 ON C.receiver_id = P3.staff_id LEFT JOIN Ref_CaseTypes CT ON C.case_type = CT.case_type_id LEFT JOIN Ref_Case_Status CS ON C.case_status = CS.status_id;
CREATE VIEW View_General_Full AS SELECT G.doc_id AS '送文編號', G.report_date AS '陳報日期', P1.staff_name AS '送文人員', D.dept_name AS '業務單位', GC.gen_cat_name AS '分類', G.subject AS '陳報主旨', P2.staff_name AS '陳報人', CASE WHEN G.is_reported = 1 THEN '是' ELSE '否' END AS '紙本', CASE WHEN G.is_electronic = 1 THEN '是' ELSE '否' END AS '電子檔' FROM Document_General G LEFT JOIN Ref_Personnel P1 ON G.sender_id = P1.staff_id LEFT JOIN Ref_Personnel P2 ON G.processor_id = P2.staff_id LEFT JOIN Ref_Departments D ON G.dept_id = D.dept_id LEFT JOIN Ref_General_Category GC ON G.gen_cat_id = GC.gen_cat_id;

PRAGMA foreign_keys = ON;
VACUUM;