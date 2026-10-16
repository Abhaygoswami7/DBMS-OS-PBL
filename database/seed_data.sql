-- ==============================================================================
-- PROJECT: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
-- MODULE: Comprehensive Synthetic Seed Data (100% Synthetic Identifiers)
--
-- STRICT ARCHITECTURAL & LEGAL GUARDRAILS COMPLIANCE:
-- - ALL identifiers are synthetic (DEM-UK-2026-0001 to DEM-UK-2026-0060).
-- - Zero real personal or government data.
-- - Logistics only: Booths, Slots, Allocations, Concurrency Logs, Telemetry.
-- ==============================================================================

USE `smart_poll_allocation_db`;

SET FOREIGN_KEY_CHECKS = 0;

-- Clean existing data
TRUNCATE TABLE `os_concurrency_audit`;
TRUNCATE TABLE `crowd_telemetry`;
TRUNCATE TABLE `simulated_verifications`;
TRUNCATE TABLE `slot_allocations`;
TRUNCATE TABLE `time_slots`;
TRUNCATE TABLE `election_events`;
TRUNCATE TABLE `voters`;
TRUNCATE TABLE `polling_booths`;
TRUNCATE TABLE `polling_stations`;
TRUNCATE TABLE `constituencies`;
TRUNCATE TABLE `states`;

SET FOREIGN_KEY_CHECKS = 1;

-- ==============================================================================
-- 1. SEED STATES
-- ==============================================================================
INSERT INTO `states` (`state_id`, `state_code`, `state_name`) VALUES
(1, 'UK', 'Uttarakhand');

-- ==============================================================================
-- 2. SEED CONSTITUENCIES (One Nation One Election: Lok Sabha & Vidhan Sabha)
-- ==============================================================================
-- Parliamentary Constituencies (Lok Sabha)
INSERT INTO `constituencies` (`constituency_id`, `state_id`, `constituency_code`, `constituency_name`, `constituency_type`, `parent_pc_id`, `total_registered_voters`) VALUES
(1, 1, 'PC-UK-01', 'Haridwar Parliamentary Constituency', 'PARLIAMENTARY', NULL, 1680000),
(2, 1, 'PC-UK-02', 'Tehri Garhwal Parliamentary Constituency', 'PARLIAMENTARY', NULL, 1540000);

-- Assembly Constituencies (Vidhan Sabha nested under PCs)
INSERT INTO `constituencies` (`constituency_id`, `state_id`, `constituency_code`, `constituency_name`, `constituency_type`, `parent_pc_id`, `total_registered_voters`) VALUES
(3, 1, 'AC-UK-01', 'Dehradun Cantt Assembly Constituency', 'ASSEMBLY', 2, 138000),
(4, 1, 'AC-UK-02', 'Rajpur Road Assembly Constituency', 'ASSEMBLY', 2, 125000),
(5, 1, 'AC-UK-03', 'Rishikesh Assembly Constituency', 'ASSEMBLY', 1, 152000),
(6, 1, 'AC-UK-04', 'BHEL Ranipur Assembly Constituency', 'ASSEMBLY', 1, 164000);

-- ==============================================================================
-- 3. SEED POLLING STATIONS (Physical premises with accessibility infrastructure)
-- ==============================================================================
INSERT INTO `polling_stations` (`station_id`, `station_code`, `station_name`, `address`, `pincode`, `latitude`, `longitude`, `total_booths`, `has_wheelchair_ramp`, `has_separate_entry_exit`) VALUES
(1, 'STN-DDN-01', 'Government Inter College Garhi Cantt', 'Cantt Board Road, Garhi Cantt, Dehradun', '248003', 30.3421500, 78.0214800, 2, 1, 1),
(2, 'STN-DDN-02', 'Kendriya Vidyalaya Hathibarkala', 'New Cantt Road, Hathibarkala Salwala, Dehradun', '248001', 30.3398200, 78.0487100, 2, 1, 1),
(3, 'STN-RKH-01', 'Punjab Sind Kshetra Inter College', 'Veerbhadra Road, Rishikesh', '249201', 30.1034200, 78.2947100, 2, 1, 1),
(4, 'STN-HWR-01', 'Delhi Public School BHEL Complex', 'Sector 3, BHEL Township, Ranipur, Haridwar', '249403', 29.9325400, 78.1189200, 2, 1, 1);

-- ==============================================================================
-- 4. SEED POLLING BOOTHS (Concurrently mapped to Parliamentary and Assembly)
-- ==============================================================================
INSERT INTO `polling_booths` (`booth_id`, `station_id`, `pc_id`, `ac_id`, `booth_number`, `booth_name`, `room_number`, `max_capacity_per_slot`, `evm_units_count`, `is_active`) VALUES
-- Station 1: Dehradun Cantt
(1, 1, 2, 3, 'BOOTH-01', 'Garhi Cantt North Wing Room 101', 'Room 101', 40, 2, 1),
(2, 1, 2, 3, 'BOOTH-02', 'Garhi Cantt South Wing Room 102', 'Room 102', 40, 2, 1),

-- Station 2: Rajpur Road
(3, 2, 2, 4, 'BOOTH-01', 'Hathibarkala Primary Section Counter A', 'Room 12', 45, 2, 1),
(4, 2, 2, 4, 'BOOTH-02', 'Hathibarkala Senior Wing Counter B', 'Room 15', 45, 2, 1),

-- Station 3: Rishikesh
(5, 3, 1, 5, 'BOOTH-01', 'Veerbhadra Academic Block Booth 1', 'Hall A', 50, 2, 1),
(6, 3, 1, 5, 'BOOTH-02', 'Veerbhadra Science Block Booth 2', 'Lab 2', 50, 2, 1),

-- Station 4: BHEL Ranipur
(7, 4, 1, 6, 'BOOTH-01', 'BHEL Sector 3 Senior Secondary Room 1', 'Room 104', 50, 2, 1),
(8, 4, 1, 6, 'BOOTH-02', 'BHEL Sector 3 Senior Secondary Room 2', 'Room 108', 50, 2, 1);

-- ==============================================================================
-- 5. SEED ELECTION EVENT (One Nation One Election Simultaneous Cycle)
-- ==============================================================================
INSERT INTO `election_events` (`event_id`, `event_name`, `event_type`, `election_date`, `start_time`, `end_time`, `status`) VALUES
(1, 'One Nation One Election - Simultaneous Lok Sabha & Vidhan Sabha Election 2026', 'ONOE_SIMULTANEOUS', '2026-11-15', '07:00:00', '18:00:00', 'SCHEDULED');

-- ==============================================================================
-- 6. SEED TIME SLOTS (4 Slots per Booth on Election Day)
-- ==============================================================================
INSERT INTO `time_slots` (`slot_id`, `booth_id`, `event_id`, `slot_date`, `start_time`, `end_time`, `max_capacity`, `allocated_count`, `priority_reserved_capacity`, `status`) VALUES
-- Booth 1 Slots
(1,  1, 1, '2026-11-15', '07:00:00', '09:30:00', 40, 0, 10, 'OPEN'),
(2,  1, 1, '2026-11-15', '09:30:00', '12:00:00', 40, 0, 10, 'OPEN'),
(3,  1, 1, '2026-11-15', '12:30:00', '15:00:00', 40, 0, 10, 'OPEN'),
(4,  1, 1, '2026-11-15', '15:00:00', '17:30:00', 40, 0, 10, 'OPEN'),

-- Booth 2 Slots
(5,  2, 1, '2026-11-15', '07:00:00', '09:30:00', 40, 0, 10, 'OPEN'),
(6,  2, 1, '2026-11-15', '09:30:00', '12:00:00', 40, 0, 10, 'OPEN'),
(7,  2, 1, '2026-11-15', '12:30:00', '15:00:00', 40, 0, 10, 'OPEN'),
(8,  2, 1, '2026-11-15', '15:00:00', '17:30:00', 40, 0, 10, 'OPEN'),

-- Booth 3 Slots
(9,  3, 1, '2026-11-15', '07:00:00', '09:30:00', 45, 0, 12, 'OPEN'),
(10, 3, 1, '2026-11-15', '09:30:00', '12:00:00', 45, 0, 12, 'OPEN'),
(11, 3, 1, '2026-11-15', '12:30:00', '15:00:00', 45, 0, 12, 'OPEN'),
(12, 3, 1, '2026-11-15', '15:00:00', '17:30:00', 45, 0, 12, 'OPEN'),

-- Booth 4 Slots
(13, 4, 1, '2026-11-15', '07:00:00', '09:30:00', 45, 0, 12, 'OPEN'),
(14, 4, 1, '2026-11-15', '09:30:00', '12:00:00', 45, 0, 12, 'OPEN'),
(15, 4, 1, '2026-11-15', '12:30:00', '15:00:00', 45, 0, 12, 'OPEN'),
(16, 4, 1, '2026-11-15', '15:00:00', '17:30:00', 45, 0, 12, 'OPEN'),

-- Booth 5 Slots
(17, 5, 1, '2026-11-15', '07:00:00', '09:30:00', 50, 0, 15, 'OPEN'),
(18, 5, 1, '2026-11-15', '09:30:00', '12:00:00', 50, 0, 15, 'OPEN'),
(19, 5, 1, '2026-11-15', '12:30:00', '15:00:00', 50, 0, 15, 'OPEN'),
(20, 5, 1, '2026-11-15', '15:00:00', '17:30:00', 50, 0, 15, 'OPEN'),

-- Booth 6 Slots
(21, 6, 1, '2026-11-15', '07:00:00', '09:30:00', 50, 0, 15, 'OPEN'),
(22, 6, 1, '2026-11-15', '09:30:00', '12:00:00', 50, 0, 15, 'OPEN'),
(23, 6, 1, '2026-11-15', '12:30:00', '15:00:00', 50, 0, 15, 'OPEN'),
(24, 6, 1, '2026-11-15', '15:00:00', '17:30:00', 50, 0, 15, 'OPEN'),

-- Booth 7 Slots
(25, 7, 1, '2026-11-15', '07:00:00', '09:30:00', 50, 0, 15, 'OPEN'),
(26, 7, 1, '2026-11-15', '09:30:00', '12:00:00', 50, 0, 15, 'OPEN'),
(27, 7, 1, '2026-11-15', '12:30:00', '15:00:00', 50, 0, 15, 'OPEN'),
(28, 7, 1, '2026-11-15', '15:00:00', '17:30:00', 50, 0, 15, 'OPEN'),

-- Booth 8 Slots
(29, 8, 1, '2026-11-15', '07:00:00', '09:30:00', 50, 0, 15, 'OPEN'),
(30, 8, 1, '2026-11-15', '09:30:00', '12:00:00', 50, 0, 15, 'OPEN'),
(31, 8, 1, '2026-11-15', '12:30:00', '15:00:00', 50, 0, 15, 'OPEN'),
(32, 8, 1, '2026-11-15', '15:00:00', '17:30:00', 50, 0, 15, 'OPEN');

-- ==============================================================================
-- 7. SEED SYNTHETIC VOTERS (DEM-UK-2026-0001 to DEM-UK-2026-0060)
-- Diverse categories: SENIOR_CITIZEN (P1), PWD (P1), PREGNANT (P1), GENERAL (P3)
-- ==============================================================================
INSERT INTO `voters` (`voter_id`, `demo_epic_no`, `full_name`, `dob`, `gender`, `address_zone`, `pincode`, `special_category`, `priority_level`, `simulated_verification_status`, `assigned_booth_id`) VALUES
-- Booth 1 (Garhi Cantt Booth 1) Voters
(1,  'DEM-UK-2026-0001', 'Ramesh Chandra Sharma', '1948-03-14', 'MALE',   'Garhi Cantt Sector 1', '248003', 'SENIOR_CITIZEN',          1, 'SIMULATED_VERIFIED', 1),
(2,  'DEM-UK-2026-0002', 'Sunita Devi Rawat',     '1952-07-21', 'FEMALE', 'Garhi Cantt Sector 1', '248003', 'SENIOR_CITIZEN',          1, 'SIMULATED_VERIFIED', 1),
(3,  'DEM-UK-2026-0003', 'Arvind Singh Negi',     '1985-11-05', 'MALE',   'Garhi Cantt Sector 2', '248003', 'PERSON_WITH_DISABILITY',  1, 'SIMULATED_VERIFIED', 1),
(4,  'DEM-UK-2026-0004', 'Deepa Joshi',           '1995-02-18', 'FEMALE', 'Garhi Cantt Sector 2', '248003', 'PREGNANT_WOMEN',          1, 'SIMULATED_VERIFIED', 1),
(5,  'DEM-UK-2026-0005', 'Manmohan Singh Bisht',  '1990-09-12', 'MALE',   'Garhi Cantt Sector 3', '248003', 'GENERAL',                  3, 'SIMULATED_VERIFIED', 1),
(6,  'DEM-UK-2026-0006', 'Pooja Bhatt',           '1994-06-25', 'FEMALE', 'Garhi Cantt Sector 3', '248003', 'GENERAL',                  3, 'SIMULATED_VERIFIED', 1),
(7,  'DEM-UK-2026-0007', 'Vikram Pant',           '1988-12-30', 'MALE',   'Garhi Cantt Sector 4', '248003', 'GENERAL',                  3, 'UNVERIFIED',         1),
(8,  'DEM-UK-2026-0008', 'Neelam Chauhan',        '1982-04-16', 'FEMALE', 'Garhi Cantt Sector 4', '248003', 'GENERAL',                  3, 'SIMULATED_VERIFIED', 1),

-- Booth 2 (Garhi Cantt Booth 2) Voters
(9,  'DEM-UK-2026-0009', 'Bhagwati Prasad Uniyal','1945-10-09', 'MALE',   'Garhi Cantt Officers Qtr', '248003', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 2),
(10, 'DEM-UK-2026-0010', 'Kamla Devi Khanduri',   '1950-01-14', 'FEMALE', 'Garhi Cantt Officers Qtr', '248003', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 2),
(11, 'DEM-UK-2026-0011', 'Suresh Kumar Thapa',    '1983-08-22', 'MALE',   'Birpur Cantt Lane 2',      '248003', 'PERSON_WITH_DISABILITY', 1, 'SIMULATED_VERIFIED', 2),
(12, 'DEM-UK-2026-0012', 'Anjali Gurung',         '1997-03-31', 'FEMALE', 'Birpur Cantt Lane 3',      '248003', 'GENERAL',                 3, 'SIMULATED_VERIFIED', 2),
(13, 'DEM-UK-2026-0013', 'Gaurav Semwal',         '1992-05-19', 'MALE',   'Birpur Cantt Lane 4',      '248003', 'GENERAL',                 3, 'UNVERIFIED',         2),
(14, 'DEM-UK-2026-0014', 'Meenakshi Thapliyal',   '1989-11-27', 'FEMALE', 'Birpur Cantt Lane 5',      '248003', 'GENERAL',                 3, 'SIMULATED_VERIFIED', 2),
(15, 'DEM-UK-2026-0015', 'Rohit Gairola',         '1991-07-08', 'MALE',   'Tapkeshwar Road',          '248003', 'GENERAL',                 3, 'SIMULATED_VERIFIED', 2),
(16, 'DEM-UK-2026-0016', 'Kavita Nautiyal',       '1996-09-14', 'FEMALE', 'Tapkeshwar Road',          '248003', 'PREGNANT_WOMEN',         1, 'SIMULATED_VERIFIED', 2),

-- Booth 3 (Hathibarkala Booth 1) Voters
(17, 'DEM-UK-2026-0017', 'Dharam Singh Rana',     '1947-06-18', 'MALE',   'Hathibarkala Block A', '248001', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 3),
(18, 'DEM-UK-2026-0018', 'Shanti Devi Panwar',    '1951-12-03', 'FEMALE', 'Hathibarkala Block A', '248001', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 3),
(19, 'DEM-UK-2026-0019', 'Naveen Chandra Tiwari', '1980-04-29', 'MALE',   'Hathibarkala Block B', '248001', 'GENERAL',                3, 'SIMULATED_VERIFIED', 3),
(20, 'DEM-UK-2026-0020', 'Rachna Dobhal',         '1986-09-15', 'FEMALE', 'Hathibarkala Block B', '248001', 'GENERAL',                3, 'SIMULATED_VERIFIED', 3),
(21, 'DEM-UK-2026-0021', 'Pankaj Sundriyal',     '1993-01-20', 'MALE',   'Salwala Main Road',    '248001', 'PERSON_WITH_DISABILITY', 1, 'SIMULATED_VERIFIED', 3),
(22, 'DEM-UK-2026-0022', 'Monika Gusain',         '1998-11-11', 'FEMALE', 'Salwala Main Road',    '248001', 'GENERAL',                3, 'UNVERIFIED',         3),
(23, 'DEM-UK-2026-0023', 'Ashok Kumar Badoni',    '1975-08-04', 'MALE',   'New Cantt Road',       '248001', 'GENERAL',                3, 'SIMULATED_VERIFIED', 3),
(24, 'DEM-UK-2026-0024', 'Sarita Maletha',        '1981-02-23', 'FEMALE', 'New Cantt Road',       '248001', 'GENERAL',                3, 'SIMULATED_VERIFIED', 3),

-- Booth 4 (Hathibarkala Booth 2) Voters
(25, 'DEM-UK-2026-0025', 'Trilok Chand Dabral',   '1949-05-30', 'MALE',   'Survey of India Colony', '248001', 'SENIOR_CITIZEN', 1, 'SIMULATED_VERIFIED', 4),
(26, 'DEM-UK-2026-0026', 'Usha Dabral',           '1953-09-17', 'FEMALE', 'Survey of India Colony', '248001', 'SENIOR_CITIZEN', 1, 'SIMULATED_VERIFIED', 4),
(27, 'DEM-UK-2026-0027', 'Himanshu Pokhriyal',    '1987-10-10', 'MALE',   'Survey Estate Lane 1',   '248001', 'GENERAL',        3, 'SIMULATED_VERIFIED', 4),
(28, 'DEM-UK-2026-0028', 'Priyanka Raturi',       '1992-06-06', 'FEMALE', 'Survey Estate Lane 2',   '248001', 'PREGNANT_WOMEN', 1, 'SIMULATED_VERIFIED', 4),
(29, 'DEM-UK-2026-0029', 'Vipin Balodi',          '1990-03-25', 'MALE',   'Rajpur Enclave',         '248001', 'GENERAL',        3, 'UNVERIFIED',         4),
(30, 'DEM-UK-2026-0030', 'Rashmi Kaintura',       '1994-12-14', 'FEMALE', 'Rajpur Enclave',         '248001', 'GENERAL',        3, 'SIMULATED_VERIFIED', 4),

-- Booth 5 (Rishikesh Booth 1) Voters
(31, 'DEM-UK-2026-0031', 'Jagdish Prasad Bahuguna','1946-04-12', 'MALE',   'Veerbhadra Colony Sector 1', '249201', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 5),
(32, 'DEM-UK-2026-0032', 'Maya Devi Dimri',       '1950-08-20', 'FEMALE', 'Veerbhadra Colony Sector 1', '249201', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 5),
(33, 'DEM-UK-2026-0033', 'Kailash Chandra Sati',  '1979-01-16', 'MALE',   'Veerbhadra Colony Sector 2', '249201', 'PERSON_WITH_DISABILITY', 1, 'SIMULATED_VERIFIED', 5),
(34, 'DEM-UK-2026-0034', 'Shweta Maithani',       '1996-07-28', 'FEMALE', 'Barrage Road Rishikesh',     '249201', 'PREGNANT_WOMEN',         1, 'SIMULATED_VERIFIED', 5),
(35, 'DEM-UK-2026-0035', 'Manish Purohit',        '1988-11-02', 'MALE',   'Barrage Road Rishikesh',     '249201', 'GENERAL',                3, 'SIMULATED_VERIFIED', 5),
(36, 'DEM-UK-2026-0036', 'Archana Chamoli',       '1991-03-19', 'FEMALE', 'Ganga Nagar Rishikesh',      '249201', 'GENERAL',                3, 'SIMULATED_VERIFIED', 5),
(37, 'DEM-UK-2026-0037', 'Sanjay Bhatt',          '1985-05-14', 'MALE',   'Ganga Nagar Rishikesh',      '249201', 'GENERAL',                3, 'UNVERIFIED',         5),
(38, 'DEM-UK-2026-0038', 'Bhavna Kothari',        '1995-10-24', 'FEMALE', 'Awas Vikas Rishikesh',       '249201', 'GENERAL',                3, 'SIMULATED_VERIFIED', 5),

-- Booth 6 (Rishikesh Booth 2) Voters
(39, 'DEM-UK-2026-0039', 'Harish Chandra Kukreti', '1944-02-17', 'MALE',   'IDPL Colony Sector A', '249201', 'SENIOR_CITIZEN', 1, 'SIMULATED_VERIFIED', 6),
(40, 'DEM-UK-2026-0040', 'Savitri Kukreti',       '1948-11-09', 'FEMALE', 'IDPL Colony Sector A', '249201', 'SENIOR_CITIZEN', 1, 'SIMULATED_VERIFIED', 6),
(41, 'DEM-UK-2026-0041', 'Deepak Lingwal',        '1984-06-30', 'MALE',   'IDPL Colony Sector B', '249201', 'GENERAL',        3, 'SIMULATED_VERIFIED', 6),
(42, 'DEM-UK-2026-0042', 'Garima Semwal',         '1993-08-12', 'FEMALE', 'IDPL Colony Sector C', '249201', 'GENERAL',        3, 'SIMULATED_VERIFIED', 6),
(43, 'DEM-UK-2026-0043', 'Vijay Pal Rawat',       '1981-12-05', 'MALE',   'Shyampur Bypass',      '249201', 'GENERAL',        3, 'UNVERIFIED',         6),
(44, 'DEM-UK-2026-0044', 'Nisha Payal',           '1997-04-18', 'FEMALE', 'Shyampur Bypass',      '249201', 'PREGNANT_WOMEN', 1, 'SIMULATED_VERIFIED', 6),

-- Booth 7 (BHEL Ranipur Booth 1) Voters
(45, 'DEM-UK-2026-0045', 'Bishambhar Dutt Joshi', '1943-09-23', 'MALE',   'BHEL Sector 3 Type 2 Qtr', '249403', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 7),
(46, 'DEM-UK-2026-0046', 'Parvati Joshi',         '1947-03-11', 'FEMALE', 'BHEL Sector 3 Type 2 Qtr', '249403', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 7),
(47, 'DEM-UK-2026-0047', 'Naresh Kumar Chauhan',  '1982-07-14', 'MALE',   'BHEL Sector 3 Type 3 Qtr', '249403', 'PERSON_WITH_DISABILITY', 1, 'SIMULATED_VERIFIED', 7),
(48, 'DEM-UK-2026-0048', 'Vandana Chauhan',       '1986-10-29', 'FEMALE', 'BHEL Sector 3 Type 3 Qtr', '249403', 'GENERAL',                3, 'SIMULATED_VERIFIED', 7),
(49, 'DEM-UK-2026-0049', 'Alok Kumar Verma',      '1990-01-08', 'MALE',   'BHEL Sector 4 Hospital Rd','249403', 'GENERAL',                3, 'SIMULATED_VERIFIED', 7),
(50, 'DEM-UK-2026-0050', 'Ritika Verma',          '1994-05-16', 'FEMALE', 'BHEL Sector 4 Hospital Rd','249403', 'GENERAL',                3, 'UNVERIFIED',         7),
(51, 'DEM-UK-2026-0051', 'Ravi Kant Tyagi',       '1978-08-20', 'MALE',   'Ranipur Mod Haridwar',     '249403', 'GENERAL',                3, 'SIMULATED_VERIFIED', 7),
(52, 'DEM-UK-2026-0052', 'Shashi Prabha Tyagi',   '1983-11-25', 'FEMALE', 'Ranipur Mod Haridwar',     '249403', 'GENERAL',                3, 'SIMULATED_VERIFIED', 7),

-- Booth 8 (BHEL Ranipur Booth 2) Voters
(53, 'DEM-UK-2026-0053', 'Madan Mohan Upadhyay',  '1945-08-15', 'MALE',   'BHEL Sector 5 Township', '249403', 'SENIOR_CITIZEN', 1, 'SIMULATED_VERIFIED', 8),
(54, 'DEM-UK-2026-0054', 'Kanta Upadhyay',        '1949-12-01', 'FEMALE', 'BHEL Sector 5 Township', '249403', 'SENIOR_CITIZEN', 1, 'SIMULATED_VERIFIED', 8),
(55, 'DEM-UK-2026-0055', 'Devendra Singh Tomar',  '1987-03-17', 'MALE',   'BHEL Sector 5 Market',   '249403', 'GENERAL',        3, 'SIMULATED_VERIFIED', 8),
(56, 'DEM-UK-2026-0056', 'Anupama Tomar',         '1991-09-22', 'FEMALE', 'BHEL Sector 5 Market',   '249403', 'GENERAL',        3, 'SIMULATED_VERIFIED', 8),
(57, 'DEM-UK-2026-0057', 'Sunil Kumar Kashyap',   '1984-04-05', 'MALE',   'Salempur Ranipur',       '249403', 'GENERAL',        3, 'SIMULATED_VERIFIED', 8),
(58, 'DEM-UK-2026-0058', 'Geeta Kashyap',         '1989-08-30', 'FEMALE', 'Salempur Ranipur',       '249403', 'PREGNANT_WOMEN', 1, 'SIMULATED_VERIFIED', 8),
(59, 'DEM-UK-2026-0059', 'Ashish Panthari',       '1993-02-14', 'MALE',   'Tibdi Road BHEL',        '249403', 'GENERAL',        3, 'UNVERIFIED',         8),
(60, 'DEM-UK-2026-0060', 'Mamta Panthari',        '1996-06-20', 'FEMALE', 'Tibdi Road BHEL',        '249403', 'GENERAL',        3, 'SIMULATED_VERIFIED', 8);

-- ==============================================================================
-- 8. SEED INITIAL SLOT ALLOCATIONS (Pre-booked test tokens for testing backend)
-- ==============================================================================
INSERT INTO `slot_allocations` (`allocation_id`, `voter_id`, `booth_id`, `slot_id`, `event_id`, `booking_reference_token`, `allocation_type`, `priority_score`, `queue_token_no`, `status`, `booked_at`) VALUES
-- Booth 1, Slot 1 (Early Morning)
(1,  1, 1, 1, 1, 'TKN-UK-1-1763180400-1001', 'USER_RESERVED', 300, 1, 'CONFIRMED', '2026-10-14 09:15:00'),
(2,  2, 1, 1, 1, 'TKN-UK-1-1763180400-1002', 'USER_RESERVED', 300, 2, 'CONFIRMED', '2026-10-14 09:20:00'),
(3,  3, 1, 1, 1, 'TKN-UK-1-1763180400-1003', 'USER_RESERVED', 300, 3, 'CONFIRMED', '2026-10-14 09:25:00'),
(4,  4, 1, 1, 1, 'TKN-UK-1-1763180400-1004', 'USER_RESERVED', 300, 4, 'CONFIRMED', '2026-10-14 09:30:00'),

-- Booth 1, Slot 2 (Late Morning)
(5,  5, 1, 2, 1, 'TKN-UK-1-1763189400-1005', 'USER_RESERVED', 100, 1, 'CONFIRMED', '2026-10-14 10:00:00'),
(6,  6, 1, 2, 1, 'TKN-UK-1-1763189400-1006', 'USER_RESERVED', 100, 2, 'CONFIRMED', '2026-10-14 10:05:00'),

-- Booth 2, Slot 5 (Early Morning)
(7,  9, 2, 5, 1, 'TKN-UK-2-1763180400-2001', 'USER_RESERVED', 300, 1, 'CONFIRMED', '2026-10-14 09:10:00'),
(8,  10, 2, 5, 1, 'TKN-UK-2-1763180400-2002', 'USER_RESERVED', 300, 2, 'CONFIRMED', '2026-10-14 09:12:00'),
(9,  11, 2, 5, 1, 'TKN-UK-2-1763180400-2003', 'USER_RESERVED', 300, 3, 'CONFIRMED', '2026-10-14 09:18:00'),

-- Booth 3, Slot 9 (Early Morning)
(10, 17, 3, 9, 1, 'TKN-UK-3-1763180400-3001', 'USER_RESERVED', 300, 1, 'CONFIRMED', '2026-10-14 08:30:00'),
(11, 18, 3, 9, 1, 'TKN-UK-3-1763180400-3002', 'USER_RESERVED', 300, 2, 'CONFIRMED', '2026-10-14 08:35:00'),
(12, 19, 3, 9, 1, 'TKN-UK-3-1763180400-3003', 'USER_RESERVED', 100, 3, 'CONFIRMED', '2026-10-14 08:40:00'),

-- Booth 5, Slot 17 (Rishikesh Early Morning)
(13, 31, 5, 17, 1, 'TKN-UK-5-1763180400-5001', 'USER_RESERVED', 300, 1, 'CONFIRMED', '2026-10-14 09:00:00'),
(14, 32, 5, 17, 1, 'TKN-UK-5-1763180400-5002', 'USER_RESERVED', 300, 2, 'CONFIRMED', '2026-10-14 09:05:00'),
(15, 33, 5, 17, 1, 'TKN-UK-5-1763180400-5003', 'USER_RESERVED', 300, 3, 'CONFIRMED', '2026-10-14 09:10:00'),

-- Booth 7, Slot 25 (Haridwar BHEL Early Morning)
(16, 45, 7, 25, 1, 'TKN-UK-7-1763180400-7001', 'USER_RESERVED', 300, 1, 'CONFIRMED', '2026-10-14 09:40:00'),
(17, 46, 7, 25, 1, 'TKN-UK-7-1763180400-7002', 'USER_RESERVED', 300, 2, 'CONFIRMED', '2026-10-14 09:45:00'),
(18, 47, 7, 25, 1, 'TKN-UK-7-1763180400-7003', 'USER_RESERVED', 300, 3, 'CONFIRMED', '2026-10-14 09:50:00');

-- ==============================================================================
-- 9. SYNCHRONIZE SLOT ALLOCATED COUNTS WITH INSERTED BOOKINGS
-- ==============================================================================
UPDATE `time_slots` s
LEFT JOIN (
    SELECT `slot_id`, COUNT(*) AS cnt
    FROM `slot_allocations`
    WHERE `status` = 'CONFIRMED'
    GROUP BY `slot_id`
) a ON s.slot_id = a.slot_id
SET s.allocated_count = COALESCE(a.cnt, 0);

-- ==============================================================================
-- 10. SEED SIMULATED VERIFICATIONS
-- Privacy Safe: Zero biometric records, simulated tokens only
-- ==============================================================================
INSERT INTO `simulated_verifications` (`verification_id`, `voter_id`, `booth_id`, `simulated_token`, `verification_method`, `status`, `failure_reason`, `verified_at`) VALUES
(1, 1,  1, 'SIM-OTP-783921', 'SIMULATED_OTP',        'PASSED', NULL, '2026-10-14 09:15:02'),
(2, 2,  1, 'SIM-EPIC-HASH-99', 'SIMULATED_EPIC_HASH', 'PASSED', NULL, '2026-10-14 09:20:01'),
(3, 3,  1, 'SIM-BIO-DEMO-01', 'DEMO_BIOMETRIC_TOKEN', 'PASSED', NULL, '2026-10-14 09:25:05'),
(4, 9,  2, 'SIM-OTP-451290', 'SIMULATED_OTP',        'PASSED', NULL, '2026-10-14 09:10:04'),
(5, 17, 3, 'SIM-OTP-662391', 'SIMULATED_OTP',        'PASSED', NULL, '2026-10-14 08:30:12');

-- ==============================================================================
-- 11. SEED CROWD TELEMETRY SENSOR LOGS (Baseline data for ML model training)
-- ==============================================================================
INSERT INTO `crowd_telemetry` (`booth_id`, `slot_id`, `timestamp`, `current_queue_length`, `avg_service_time_seconds`, `weather_condition`, `predicted_density_level`, `congestion_index`) VALUES
(1, 1, '2026-11-15 07:30:00', 4,  110, 'CLEAR', 'LOW',      10.00),
(1, 1, '2026-11-15 08:30:00', 8,  115, 'CLEAR', 'LOW',      20.00),
(1, 2, '2026-11-15 10:00:00', 22, 135, 'SUNNY', 'MODERATE', 55.00),
(1, 2, '2026-11-15 11:15:00', 36, 150, 'SUNNY', 'HIGH',     90.00),
(2, 5, '2026-11-15 08:00:00', 5,  105, 'CLEAR', 'LOW',      12.50),
(3, 9, '2026-11-15 08:15:00', 6,  112, 'CLEAR', 'LOW',      13.33),
(5, 17,'2026-11-15 08:00:00', 7,  118, 'CLEAR', 'LOW',      14.00),
(7, 25,'2026-11-15 08:30:00', 6,  122, 'CLEAR', 'LOW',      12.00);

-- ==============================================================================
-- 12. SEED OS CONCURRENCY AUDIT LOG (Demonstrating Mutex & Priority Aging)
-- ==============================================================================
INSERT INTO `os_concurrency_audit` (`thread_name`, `voter_id`, `booth_id`, `slot_id`, `operation_type`, `lock_acquired_at`, `lock_released_at`, `status_code`, `execution_latency_ms`, `details`) VALUES
('WorkerThread-1', 1, 1, 1, 'SLOT_LOCK',     '2026-10-14 09:14:59.102341', '2026-10-14 09:14:59.115421', 'LOCK_ACQUIRED', 13.080, 'Row lock acquired on time_slots for slot_id=1'),
('WorkerThread-1', 1, 1, 1, 'SLOT_RESERVE',  '2026-10-14 09:14:59.115421', '2026-10-14 09:15:00.002104', 'COMMITTED',     86.683, 'Allocated TKN-UK-1-1763180400-1001 for senior voter'),
('WorkerThread-2', 2, 1, 1, 'SLOT_LOCK',     '2026-10-14 09:19:59.501230', '2026-10-14 09:19:59.512110', 'LOCK_ACQUIRED', 10.880, 'Row lock acquired on time_slots for slot_id=1'),
('WorkerThread-2', 2, 1, 1, 'SLOT_RESERVE',  '2026-10-14 09:19:59.512110', '2026-10-14 09:20:00.012431', 'COMMITTED',     500.321, 'Allocated TKN-UK-1-1763180400-1002'),
('SchedulerAging', 5, 1, 2, 'PRIORITY_ELEVATION', NULL, NULL, 'AGING_TRIGGERED', 5.210, 'Priority aged: voter wait time exceeded threshold, priority increased to 120');
