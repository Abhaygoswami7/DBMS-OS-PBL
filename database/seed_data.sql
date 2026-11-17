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
(2, 1, 'PC-UK-02', 'Nainital-Udhamsingh Nagar Parliamentary Constituency', 'PARLIAMENTARY', NULL, 1850000);

-- Assembly Constituencies (Vidhan Sabha nested under PCs)
INSERT INTO `constituencies` (`constituency_id`, `state_id`, `constituency_code`, `constituency_name`, `constituency_type`, `parent_pc_id`, `total_registered_voters`) VALUES
(3, 1, 'AC-UK-01', 'Bhimtal Assembly Constituency', 'ASSEMBLY', 2, 125000),
(4, 1, 'AC-UK-02', 'Nainital Assembly Constituency', 'ASSEMBLY', 2, 118000),
(5, 1, 'AC-UK-03', 'Rishikesh Assembly Constituency', 'ASSEMBLY', 1, 152000),
(6, 1, 'AC-UK-04', 'BHEL Ranipur Assembly Constituency', 'ASSEMBLY', 1, 164000);

-- ==============================================================================
-- 3. SEED POLLING STATIONS (Physical premises with accessibility infrastructure)
-- Demonstration Polling Stations: Bhimtal and Nagri Gaon, Nainital District
-- ==============================================================================
INSERT INTO `polling_stations` (`station_id`, `station_code`, `station_name`, `address`, `pincode`, `latitude`, `longitude`, `total_booths`, `has_wheelchair_ramp`, `has_separate_entry_exit`) VALUES
(1, 'STN-BHM-01', 'Graphic Era Hill University, Bhimtal Campus', 'Sattal Road, Bhimtal, Nainital District', '263136', 29.3751000, 79.5313000, 2, 1, 1),
(2, 'STN-NGR-01', 'Woodbridge School', 'Dob, Lewshal, Bhowali-Bhimtal Road, near Nagri Gaon', '263132', 29.3690000, 79.5220000, 2, 1, 1),
(3, 'STN-BHM-02', 'Vikas Bhawan (District Development Complex)', 'Block Road, Bhimtal, Nainital District', '263136', 29.3602000, 79.5535000, 2, 1, 1),
(4, 'STN-BHM-03', 'Nagar Palika Parishad Office, Bhimtal', 'Lake Road, Bhimtal, Nainital District', '263136', 29.3445000, 79.5634000, 2, 1, 1);

-- ==============================================================================
-- 4. SEED POLLING BOOTHS (Concurrently mapped to Parliamentary and Assembly)
-- All booths nested under PC-UK-02 and AC-UK-01 (Bhimtal)
-- ==============================================================================
INSERT INTO `polling_booths` (`booth_id`, `station_id`, `pc_id`, `ac_id`, `booth_number`, `booth_name`, `room_number`, `max_capacity_per_slot`, `evm_units_count`, `is_active`) VALUES
-- Station 1: Graphic Era Hill University (Bhimtal / Nagri Gaon approach)
(1, 1, 2, 3, 'BOOTH-01', 'GEHU Academic Wing Room 101', 'Room 101', 40, 2, 1),
(2, 1, 2, 3, 'BOOTH-02', 'GEHU Conference Block Room 102', 'Room 102', 40, 2, 1),

-- Station 2: Woodbridge School (Nagri Gaon area)
(3, 2, 2, 3, 'BOOTH-01', 'Woodbridge Main Campus Room 1', 'Room 1', 45, 2, 1),
(4, 2, 2, 3, 'BOOTH-02', 'Woodbridge Senior Wing Room 2', 'Room 2', 45, 2, 1),

-- Station 3: Vikas Bhawan (Bhimtal area)
(5, 3, 2, 3, 'BOOTH-01', 'Vikas Bhawan Community Hall Room 1', 'Hall 1', 50, 2, 1),
(6, 3, 2, 3, 'BOOTH-02', 'Vikas Bhawan Rural Development Room 2', 'Room 201', 50, 2, 1),

-- Station 4: Nagar Palika Parishad Office (Bhimtal Lake area)
(7, 4, 2, 3, 'BOOTH-01', 'Nagar Palika Town Hall Room 1', 'Hall A', 50, 2, 1),
(8, 4, 2, 3, 'BOOTH-02', 'Nagar Palika Annex Room 2', 'Room 105', 50, 2, 1);

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
-- Distributed across Bhimtal & Nagri Gaon sectors
-- ==============================================================================
INSERT INTO `voters` (`voter_id`, `demo_epic_no`, `full_name`, `dob`, `gender`, `address_zone`, `pincode`, `special_category`, `priority_level`, `simulated_verification_status`, `assigned_booth_id`) VALUES
-- Booth 1 (Graphic Era Hill Univ - Room 101) Voters
(1,  'DEM-UK-2026-0001', 'Ramesh Chandra Sharma', '1948-03-14', 'MALE',   'Sattal Road Sector 1, Bhimtal', '263136', 'SENIOR_CITIZEN',          1, 'SIMULATED_VERIFIED', 1),
(2,  'DEM-UK-2026-0002', 'Sunita Devi Rawat',     '1952-07-21', 'FEMALE', 'Sattal Road Sector 1, Bhimtal', '263136', 'SENIOR_CITIZEN',          1, 'SIMULATED_VERIFIED', 1),
(3,  'DEM-UK-2026-0003', 'Arvind Singh Negi',     '1985-11-05', 'MALE',   'Sattal Road Sector 2, Bhimtal', '263136', 'PERSON_WITH_DISABILITY',  1, 'SIMULATED_VERIFIED', 1),
(4,  'DEM-UK-2026-0004', 'Deepa Joshi',           '1995-02-18', 'FEMALE', 'Sattal Road Sector 2, Bhimtal', '263136', 'PREGNANT_WOMEN',          1, 'SIMULATED_VERIFIED', 1),
(5,  'DEM-UK-2026-0005', 'Manmohan Singh Bisht',  '1990-09-12', 'MALE',   'Sattal Road Sector 3, Bhimtal', '263136', 'GENERAL',                  3, 'SIMULATED_VERIFIED', 1),
(6,  'DEM-UK-2026-0006', 'Pooja Bhatt',           '1994-06-25', 'FEMALE', 'Sattal Road Sector 3, Bhimtal', '263136', 'GENERAL',                  3, 'SIMULATED_VERIFIED', 1),
(7,  'DEM-UK-2026-0007', 'Vikram Pant',           '1988-12-30', 'MALE',   'Sattal Road Sector 4, Bhimtal', '263136', 'GENERAL',                  3, 'UNVERIFIED',         1),
(8,  'DEM-UK-2026-0008', 'Neelam Chauhan',        '1982-04-16', 'FEMALE', 'Sattal Road Sector 4, Bhimtal', '263136', 'GENERAL',                  3, 'SIMULATED_VERIFIED', 1),

-- Booth 2 (Graphic Era Hill Univ - Room 102) Voters
(9,  'DEM-UK-2026-0009', 'Bhagwati Prasad Uniyal','1945-10-09', 'MALE',   'GEHU Campus Sector, Bhimtal',   '263136', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 2),
(10, 'DEM-UK-2026-0010', 'Kamla Devi Khanduri',   '1950-01-14', 'FEMALE', 'GEHU Campus Sector, Bhimtal',   '263136', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 2),
(11, 'DEM-UK-2026-0011', 'Suresh Kumar Thapa',    '1983-08-22', 'MALE',   'Bhimtal Hills Lane 2',          '263136', 'PERSON_WITH_DISABILITY', 1, 'SIMULATED_VERIFIED', 2),
(12, 'DEM-UK-2026-0012', 'Anjali Gurung',         '1997-03-31', 'FEMALE', 'Bhimtal Hills Lane 3',          '263136', 'GENERAL',                 3, 'SIMULATED_VERIFIED', 2),
(13, 'DEM-UK-2026-0013', 'Gaurav Semwal',         '1992-05-19', 'MALE',   'Bhimtal Hills Lane 4',          '263136', 'GENERAL',                 3, 'UNVERIFIED',         2),
(14, 'DEM-UK-2026-0014', 'Meenakshi Thapliyal',   '1989-11-27', 'FEMALE', 'Bhimtal Hills Lane 5',          '263136', 'GENERAL',                 3, 'SIMULATED_VERIFIED', 2),
(15, 'DEM-UK-2026-0015', 'Rohit Gairola',         '1991-07-08', 'MALE',   'Sattal Approach Road',          '263136', 'GENERAL',                 3, 'SIMULATED_VERIFIED', 2),
(16, 'DEM-UK-2026-0016', 'Kavita Nautiyal',       '1996-09-14', 'FEMALE', 'Sattal Approach Road',          '263136', 'PREGNANT_WOMEN',         1, 'SIMULATED_VERIFIED', 2),

-- Booth 3 (Woodbridge School - Room 1) Voters
(17, 'DEM-UK-2026-0017', 'Dharam Singh Rana',     '1947-06-18', 'MALE',   'Nagri Gaon Sector A',           '263132', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 3),
(18, 'DEM-UK-2026-0018', 'Shanti Devi Panwar',    '1951-12-03', 'FEMALE', 'Nagri Gaon Sector A',           '263132', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 3),
(19, 'DEM-UK-2026-0019', 'Naveen Chandra Tiwari', '1980-04-29', 'MALE',   'Nagri Gaon Sector B',           '263132', 'GENERAL',                3, 'SIMULATED_VERIFIED', 3),
(20, 'DEM-UK-2026-0020', 'Rachna Dobhal',         '1986-09-15', 'FEMALE', 'Nagri Gaon Sector B',           '263132', 'GENERAL',                3, 'SIMULATED_VERIFIED', 3),
(21, 'DEM-UK-2026-0021', 'Pankaj Sundriyal',     '1993-01-20', 'MALE',   'Lewshal Road, Nagri Gaon',      '263132', 'PERSON_WITH_DISABILITY', 1, 'SIMULATED_VERIFIED', 3),
(22, 'DEM-UK-2026-0022', 'Monika Gusain',         '1998-11-11', 'FEMALE', 'Lewshal Road, Nagri Gaon',      '263132', 'GENERAL',                3, 'UNVERIFIED',         3),
(23, 'DEM-UK-2026-0023', 'Ashok Kumar Badoni',    '1975-08-04', 'MALE',   'Bhowali-Bhimtal Road',          '263132', 'GENERAL',                3, 'SIMULATED_VERIFIED', 3),
(24, 'DEM-UK-2026-0024', 'Sarita Maletha',        '1981-02-23', 'FEMALE', 'Bhowali-Bhimtal Road',          '263132', 'GENERAL',                3, 'SIMULATED_VERIFIED', 3),

-- Booth 4 (Woodbridge School - Room 2) Voters
(25, 'DEM-UK-2026-0025', 'Trilok Chand Dabral',   '1949-05-30', 'MALE',   'Nagri Gaon Upper Enclave',      '263132', 'SENIOR_CITIZEN', 1, 'SIMULATED_VERIFIED', 4),
(26, 'DEM-UK-2026-0026', 'Usha Dabral',           '1953-09-17', 'FEMALE', 'Nagri Gaon Upper Enclave',      '263132', 'SENIOR_CITIZEN', 1, 'SIMULATED_VERIFIED', 4),
(27, 'DEM-UK-2026-0027', 'Himanshu Pokhriyal',    '1987-10-10', 'MALE',   'Dob Valley Lane 1',             '263132', 'GENERAL',        3, 'SIMULATED_VERIFIED', 4),
(28, 'DEM-UK-2026-0028', 'Priyanka Raturi',       '1992-06-06', 'FEMALE', 'Dob Valley Lane 2',             '263132', 'PREGNANT_WOMEN', 1, 'SIMULATED_VERIFIED', 4),
(29, 'DEM-UK-2026-0029', 'Vipin Balodi',          '1990-03-25', 'MALE',   'Bhowali Range Foothills',       '263132', 'GENERAL',        3, 'UNVERIFIED',         4),
(30, 'DEM-UK-2026-0030', 'Rashmi Kaintura',       '1994-12-14', 'FEMALE', 'Bhowali Range Foothills',       '263132', 'GENERAL',        3, 'SIMULATED_VERIFIED', 4),

-- Booth 5 (Vikas Bhawan - Room 1) Voters
(31, 'DEM-UK-2026-0031', 'Jagdish Prasad Bahuguna','1946-04-12', 'MALE',   'Block Road Sector 1, Bhimtal',  '263136', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 5),
(32, 'DEM-UK-2026-0032', 'Maya Devi Dimri',       '1950-08-20', 'FEMALE', 'Block Road Sector 1, Bhimtal',  '263136', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 5),
(33, 'DEM-UK-2026-0033', 'Kailash Chandra Sati',  '1979-01-16', 'MALE',   'Block Road Sector 2, Bhimtal',  '263136', 'PERSON_WITH_DISABILITY', 1, 'SIMULATED_VERIFIED', 5),
(34, 'DEM-UK-2026-0034', 'Shweta Maithani',       '1996-07-28', 'FEMALE', 'Vikas Bhawan Complex Lane A',  '263136', 'PREGNANT_WOMEN',         1, 'SIMULATED_VERIFIED', 5),
(35, 'DEM-UK-2026-0035', 'Manish Purohit',        '1988-11-02', 'MALE',   'Vikas Bhawan Complex Lane A',  '263136', 'GENERAL',                3, 'SIMULATED_VERIFIED', 5),
(36, 'DEM-UK-2026-0036', 'Archana Chamoli',       '1991-03-19', 'FEMALE', 'Pangot Road Junction',          '263136', 'GENERAL',                3, 'SIMULATED_VERIFIED', 5),
(37, 'DEM-UK-2026-0037', 'Sanjay Bhatt',          '1985-05-14', 'MALE',   'Pangot Road Junction',          '263136', 'GENERAL',                3, 'UNVERIFIED',         5),
(38, 'DEM-UK-2026-0038', 'Bhavna Kothari',        '1995-10-24', 'FEMALE', 'Awas Vikas Bhimtal',           '263136', 'GENERAL',                3, 'SIMULATED_VERIFIED', 5),

-- Booth 6 (Vikas Bhawan - Room 2) Voters
(39, 'DEM-UK-2026-0039', 'Harish Chandra Kukreti', '1944-02-17', 'MALE',   'Vikas Bhawan Colony Sector A',  '263136', 'SENIOR_CITIZEN', 1, 'SIMULATED_VERIFIED', 6),
(40, 'DEM-UK-2026-0040', 'Savitri Kukreti',       '1948-11-09', 'FEMALE', 'Vikas Bhawan Colony Sector A',  '263136', 'SENIOR_CITIZEN', 1, 'SIMULATED_VERIFIED', 6),
(41, 'DEM-UK-2026-0041', 'Deepak Lingwal',        '1984-06-30', 'MALE',   'Vikas Bhawan Colony Sector B',  '263136', 'GENERAL',        3, 'SIMULATED_VERIFIED', 6),
(42, 'DEM-UK-2026-0042', 'Garima Semwal',         '1993-08-12', 'FEMALE', 'Vikas Bhawan Colony Sector C',  '263136', 'GENERAL',        3, 'SIMULATED_VERIFIED', 6),
(43, 'DEM-UK-2026-0043', 'Vijay Pal Rawat',       '1981-12-05', 'MALE',   'Bhimtal Bypass Road',           '263136', 'GENERAL',        3, 'UNVERIFIED',         6),
(44, 'DEM-UK-2026-0044', 'Nisha Payal',           '1997-04-18', 'FEMALE', 'Bhimtal Bypass Road',           '263136', 'PREGNANT_WOMEN', 1, 'SIMULATED_VERIFIED', 6),

-- Booth 7 (Nagar Palika - Room 1) Voters
(45, 'DEM-UK-2026-0045', 'Bishambhar Dutt Joshi', '1943-09-23', 'MALE',   'Lake Road Sector 1, Bhimtal',   '263136', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 7),
(46, 'DEM-UK-2026-0046', 'Parvati Joshi',         '1947-03-11', 'FEMALE', 'Lake Road Sector 1, Bhimtal',   '263136', 'SENIOR_CITIZEN',         1, 'SIMULATED_VERIFIED', 7),
(47, 'DEM-UK-2026-0047', 'Naresh Kumar Chauhan',  '1982-07-14', 'MALE',   'Lake Road Sector 2, Bhimtal',   '263136', 'PERSON_WITH_DISABILITY', 1, 'SIMULATED_VERIFIED', 7),
(48, 'DEM-UK-2026-0048', 'Vandana Chauhan',       '1986-10-29', 'FEMALE', 'Lake Road Sector 2, Bhimtal',   '263136', 'GENERAL',                3, 'SIMULATED_VERIFIED', 7),
(49, 'DEM-UK-2026-0049', 'Alok Kumar Verma',      '1990-01-08', 'MALE',   'Bhimtal Lake Front Rd',         '263136', 'GENERAL',                3, 'SIMULATED_VERIFIED', 7),
(50, 'DEM-UK-2026-0050', 'Ritika Verma',          '1994-05-16', 'FEMALE', 'Bhimtal Lake Front Rd',         '263136', 'GENERAL',                3, 'UNVERIFIED',         7),
(51, 'DEM-UK-2026-0051', 'Ravi Kant Tyagi',       '1978-08-20', 'MALE',   'Mallital Main Market',          '263136', 'GENERAL',                3, 'SIMULATED_VERIFIED', 7),
(52, 'DEM-UK-2026-0052', 'Shashi Prabha Tyagi',   '1983-11-25', 'FEMALE', 'Mallital Main Market',          '263136', 'GENERAL',                3, 'SIMULATED_VERIFIED', 7),

-- Booth 8 (Nagar Palika - Room 2) Voters
(53, 'DEM-UK-2026-0053', 'Madan Mohan Upadhyay',  '1945-08-15', 'MALE',   'Bhimtal Island View Sector',    '263136', 'SENIOR_CITIZEN', 1, 'SIMULATED_VERIFIED', 8),
(54, 'DEM-UK-2026-0054', 'Kanta Upadhyay',        '1949-12-01', 'FEMALE', 'Bhimtal Island View Sector',    '263136', 'SENIOR_CITIZEN', 1, 'SIMULATED_VERIFIED', 8),
(55, 'DEM-UK-2026-0055', 'Devendra Singh Tomar',  '1987-03-17', 'MALE',   'Bhimtal Mandir Lane',           '263136', 'GENERAL',        3, 'SIMULATED_VERIFIED', 8),
(56, 'DEM-UK-2026-0056', 'Anupama Tomar',         '1991-09-22', 'FEMALE', 'Bhimtal Mandir Lane',           '263136', 'GENERAL',        3, 'SIMULATED_VERIFIED', 8),
(57, 'DEM-UK-2026-0057', 'Sunil Kumar Kashyap',   '1984-04-05', 'MALE',   'Tallital Road, Bhimtal',        '263136', 'GENERAL',        3, 'SIMULATED_VERIFIED', 8),
(58, 'DEM-UK-2026-0058', 'Geeta Kashyap',         '1989-08-30', 'FEMALE', 'Tallital Road, Bhimtal',        '263136', 'PREGNANT_WOMEN', 1, 'SIMULATED_VERIFIED', 8),
(59, 'DEM-UK-2026-0059', 'Ashish Panthari',       '1993-02-14', 'MALE',   'Nainital Road Junction',        '263136', 'GENERAL',        3, 'UNVERIFIED',         8),
(60, 'DEM-UK-2026-0060', 'Mamta Panthari',        '1996-06-20', 'FEMALE', 'Nainital Road Junction',        '263136', 'GENERAL',        3, 'SIMULATED_VERIFIED', 8);

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

-- Booth 5, Slot 17 (Vikas Bhawan Early Morning)
(13, 31, 5, 17, 1, 'TKN-UK-5-1763180400-5001', 'USER_RESERVED', 300, 1, 'CONFIRMED', '2026-10-14 09:00:00'),
(14, 32, 5, 17, 1, 'TKN-UK-5-1763180400-5002', 'USER_RESERVED', 300, 2, 'CONFIRMED', '2026-10-14 09:05:00'),
(15, 33, 5, 17, 1, 'TKN-UK-5-1763180400-5003', 'USER_RESERVED', 300, 3, 'CONFIRMED', '2026-10-14 09:10:00'),

-- Booth 7, Slot 25 (Nagar Palika Early Morning)
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
