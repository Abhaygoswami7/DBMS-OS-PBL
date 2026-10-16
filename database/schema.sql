-- ==============================================================================
-- PROJECT: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
-- MODULE: Complete MySQL 8.0+ 3NF Normalized Database Schema
--
-- STRICT ARCHITECTURAL & LEGAL GUARDRAILS COMPLIANCE:
-- 1. LOGISTICS ONLY, NOT VOTING: Manages booth allocations, simulated verification,
--    slot scheduling, and crowd prediction for simultaneous Lok Sabha & Vidhan Sabha elections.
--    Does NOT implement ballot casting, candidate selection, or vote tallying.
-- 2. PRIVACY & SYNTHETIC IDENTITY ONLY: Purely synthetic demo identifiers (DEM-UK-2026-XXXX).
--    Zero real government IDs, zero real biometric data.
-- 3. STRICT NAMING CONTRACT: Single source of truth for Flask backend, OS concurrency engine,
--    and academic project reports.
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS `smart_poll_allocation_db`
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE `smart_poll_allocation_db`;

-- Set session flags for strict standards
SET FOREIGN_KEY_CHECKS = 0;

-- Drop existing views if any
DROP VIEW IF EXISTS `vw_constituency_logistics_summary`;
DROP VIEW IF EXISTS `vw_voter_appointment_slip`;
DROP VIEW IF EXISTS `vw_booth_live_status`;

-- Drop existing tables in reverse dependency order
DROP TABLE IF EXISTS `os_concurrency_audit`;
DROP TABLE IF EXISTS `crowd_telemetry`;
DROP TABLE IF EXISTS `simulated_verifications`;
DROP TABLE IF EXISTS `slot_allocations`;
DROP TABLE IF EXISTS `time_slots`;
DROP TABLE IF EXISTS `election_events`;
DROP TABLE IF EXISTS `voters`;
DROP TABLE IF EXISTS `polling_booths`;
DROP TABLE IF EXISTS `polling_stations`;
DROP TABLE IF EXISTS `constituencies`;
DROP TABLE IF EXISTS `states`;

SET FOREIGN_KEY_CHECKS = 1;

-- ==============================================================================
-- TABLE 1: states
-- 3NF Justification: State metadata is functionally dependent solely on state_id.
-- ==============================================================================
CREATE TABLE `states` (
    `state_id` INT AUTO_INCREMENT PRIMARY KEY,
    `state_code` VARCHAR(10) NOT NULL UNIQUE,
    `state_name` VARCHAR(100) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_states_code` (`state_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Federal states participating in simultaneous elections';

-- ==============================================================================
-- TABLE 2: constituencies
-- Supports simultaneous One Nation One Election dual-constituency mapping:
-- Parliamentary Constituency (Lok Sabha) and Assembly Constituency (Vidhan Sabha).
-- 3NF: All attributes depend strictly on constituency_id.
-- ==============================================================================
CREATE TABLE `constituencies` (
    `constituency_id` INT AUTO_INCREMENT PRIMARY KEY,
    `state_id` INT NOT NULL,
    `constituency_code` VARCHAR(20) NOT NULL UNIQUE,
    `constituency_name` VARCHAR(120) NOT NULL,
    `constituency_type` ENUM('PARLIAMENTARY', 'ASSEMBLY') NOT NULL,
    `parent_pc_id` INT NULL COMMENT 'Hierarchical link: Assembly Constituency nested within Parliamentary Constituency',
    `total_registered_voters` INT DEFAULT 0,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_constituencies_state`
        FOREIGN KEY (`state_id`) REFERENCES `states` (`state_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_constituencies_parent_pc`
        FOREIGN KEY (`parent_pc_id`) REFERENCES `constituencies` (`constituency_id`)
        ON UPDATE CASCADE ON DELETE SET NULL,
    INDEX `idx_constituency_type` (`constituency_type`),
    INDEX `idx_constituency_parent` (`parent_pc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Lok Sabha & Vidhan Sabha constituencies';

-- ==============================================================================
-- TABLE 3: polling_stations
-- Physical facility / campus hosting multiple booths.
-- 3NF: Station physical address and geospatial data depend solely on station_id.
-- ==============================================================================
CREATE TABLE `polling_stations` (
    `station_id` INT AUTO_INCREMENT PRIMARY KEY,
    `station_code` VARCHAR(20) NOT NULL UNIQUE,
    `station_name` VARCHAR(150) NOT NULL,
    `address` VARCHAR(255) NOT NULL,
    `pincode` VARCHAR(10) NOT NULL,
    `latitude` DECIMAL(10, 7) NOT NULL,
    `longitude` DECIMAL(10, 7) NOT NULL,
    `total_booths` INT NOT NULL DEFAULT 1,
    `has_wheelchair_ramp` TINYINT(1) NOT NULL DEFAULT 1,
    `has_separate_entry_exit` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_stations_pincode` (`pincode`),
    INDEX `idx_stations_geo` (`latitude`, `longitude`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Physical facilities hosting polling booths';

-- ==============================================================================
-- TABLE 4: polling_booths
-- Specific room/counter inside a polling station.
-- In One Nation One Election, each booth concurrently handles both Parliamentary (PC)
-- and Assembly (AC) logistics for its mapped voter group.
-- 3NF: All booth specifications depend strictly on booth_id.
-- ==============================================================================
CREATE TABLE `polling_booths` (
    `booth_id` INT AUTO_INCREMENT PRIMARY KEY,
    `station_id` INT NOT NULL,
    `pc_id` INT NOT NULL COMMENT 'Associated Lok Sabha Parliamentary Constituency',
    `ac_id` INT NOT NULL COMMENT 'Associated Vidhan Sabha Assembly Constituency',
    `booth_number` VARCHAR(20) NOT NULL,
    `booth_name` VARCHAR(120) NOT NULL,
    `room_number` VARCHAR(30) NOT NULL,
    `max_capacity_per_slot` INT NOT NULL DEFAULT 50,
    `evm_units_count` INT NOT NULL DEFAULT 2 COMMENT '1 PC Ballot Unit + 1 AC Ballot Unit + Control Units',
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_booths_station`
        FOREIGN KEY (`station_id`) REFERENCES `polling_stations` (`station_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_booths_pc`
        FOREIGN KEY (`pc_id`) REFERENCES `constituencies` (`constituency_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_booths_ac`
        FOREIGN KEY (`ac_id`) REFERENCES `constituencies` (`constituency_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `uq_station_booth_num`
        UNIQUE (`station_id`, `booth_number`),
    INDEX `idx_booths_pc` (`pc_id`),
    INDEX `idx_booths_ac` (`ac_id`),
    INDEX `idx_booths_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Individual polling counters/rooms mapped to PC and AC';

-- ==============================================================================
-- TABLE 5: voters
-- Synthetic Demo Registry ONLY.
-- GUARDRAIL COMPLIANCE: demo_epic_no format = 'DEM-UK-2026-XXXX'.
-- No real citizen data, no real government identifiers.
-- 3NF: All attributes depend on voter_id.
-- ==============================================================================
CREATE TABLE `voters` (
    `voter_id` INT AUTO_INCREMENT PRIMARY KEY,
    `demo_epic_no` VARCHAR(25) NOT NULL UNIQUE COMMENT 'Synthetic Identifier format: DEM-UK-2026-XXXX',
    `full_name` VARCHAR(120) NOT NULL,
    `dob` DATE NOT NULL,
    `gender` ENUM('MALE', 'FEMALE', 'OTHER') NOT NULL,
    `address_zone` VARCHAR(100) NOT NULL,
    `pincode` VARCHAR(10) NOT NULL,
    `special_category` ENUM('GENERAL', 'SENIOR_CITIZEN', 'PERSON_WITH_DISABILITY', 'PREGNANT_WOMEN') NOT NULL DEFAULT 'GENERAL',
    `priority_level` TINYINT NOT NULL DEFAULT 3 COMMENT '1=Highest (Senior/PwD/Pregnant), 2=Elevated, 3=Normal General',
    `simulated_verification_status` ENUM('UNVERIFIED', 'SIMULATED_VERIFIED', 'FLAGGED') NOT NULL DEFAULT 'UNVERIFIED',
    `assigned_booth_id` INT NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_voters_booth`
        FOREIGN KEY (`assigned_booth_id`) REFERENCES `polling_booths` (`booth_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX `idx_voters_demo_epic` (`demo_epic_no`),
    INDEX `idx_voters_priority` (`priority_level`),
    INDEX `idx_voters_category` (`special_category`),
    INDEX `idx_voters_booth` (`assigned_booth_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Synthetic voter identities and priority classifications';

-- ==============================================================================
-- TABLE 6: election_events
-- Defines simultaneous election cycles.
-- 3NF: Event temporal and state properties depend solely on event_id.
-- ==============================================================================
CREATE TABLE `election_events` (
    `event_id` INT AUTO_INCREMENT PRIMARY KEY,
    `event_name` VARCHAR(150) NOT NULL,
    `event_type` ENUM('ONOE_SIMULTANEOUS', 'LOK_SABHA_ONLY', 'VIDHAN_SABHA_ONLY') NOT NULL DEFAULT 'ONOE_SIMULTANEOUS',
    `election_date` DATE NOT NULL,
    `start_time` TIME NOT NULL DEFAULT '07:00:00',
    `end_time` TIME NOT NULL DEFAULT '18:00:00',
    `status` ENUM('SCHEDULED', 'ACTIVE', 'COMPLETED', 'ARCHIVED') NOT NULL DEFAULT 'SCHEDULED',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_event_date` (`election_date`),
    INDEX `idx_event_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Election event logistics metadata';

-- ==============================================================================
-- TABLE 7: time_slots
-- Granular time windows assigned to each polling booth to flatten the arrival curve.
-- Integrates OS-style priority capacity reservation.
-- 3NF: Dependent strictly on slot_id.
-- ==============================================================================
CREATE TABLE `time_slots` (
    `slot_id` INT AUTO_INCREMENT PRIMARY KEY,
    `booth_id` INT NOT NULL,
    `event_id` INT NOT NULL,
    `slot_date` DATE NOT NULL,
    `start_time` TIME NOT NULL,
    `end_time` TIME NOT NULL,
    `max_capacity` INT NOT NULL DEFAULT 60,
    `allocated_count` INT NOT NULL DEFAULT 0,
    `priority_reserved_capacity` INT NOT NULL DEFAULT 15 COMMENT 'Reserved capacity for Priority 1 voters',
    `status` ENUM('OPEN', 'FULL', 'FAST_TRACK_ONLY', 'CLOSED') NOT NULL DEFAULT 'OPEN',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_slots_booth`
        FOREIGN KEY (`booth_id`) REFERENCES `polling_booths` (`booth_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_slots_event`
        FOREIGN KEY (`event_id`) REFERENCES `election_events` (`event_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `uq_booth_event_timeslot`
        UNIQUE (`booth_id`, `event_id`, `slot_date`, `start_time`),
    INDEX `idx_slots_booth_status` (`booth_id`, `status`),
    INDEX `idx_slots_date_time` (`slot_date`, `start_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Discretized time slots with priority quotas per booth';

-- ==============================================================================
-- TABLE 8: slot_allocations
-- Concurrency-safe voter reservations and queue tokens.
-- 3NF: Allocation status and timestamps depend solely on allocation_id.
-- ==============================================================================
CREATE TABLE `slot_allocations` (
    `allocation_id` INT AUTO_INCREMENT PRIMARY KEY,
    `voter_id` INT NOT NULL,
    `booth_id` INT NOT NULL,
    `slot_id` INT NOT NULL,
    `event_id` INT NOT NULL,
    `booking_reference_token` VARCHAR(64) NOT NULL UNIQUE COMMENT 'Cryptographically secure synthetic token',
    `allocation_type` ENUM('USER_RESERVED', 'ALGORITHMIC_ALLOCATED', 'EMERGENCY_WALKIN') NOT NULL DEFAULT 'USER_RESERVED',
    `priority_score` INT NOT NULL DEFAULT 0 COMMENT 'Calculated priority score factoring category and wait age',
    `queue_token_no` INT NOT NULL COMMENT 'Sequential queue number within the specific slot',
    `status` ENUM('CONFIRMED', 'CHECKED_IN', 'COMPLETED', 'CANCELLED', 'NO_SHOW') NOT NULL DEFAULT 'CONFIRMED',
    `booked_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `check_in_time` TIMESTAMP NULL DEFAULT NULL,
    `check_out_time` TIMESTAMP NULL DEFAULT NULL,
    CONSTRAINT `fk_alloc_voter`
        FOREIGN KEY (`voter_id`) REFERENCES `voters` (`voter_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_alloc_booth`
        FOREIGN KEY (`booth_id`) REFERENCES `polling_booths` (`booth_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_alloc_slot`
        FOREIGN KEY (`slot_id`) REFERENCES `time_slots` (`slot_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_alloc_event`
        FOREIGN KEY (`event_id`) REFERENCES `election_events` (`event_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX `idx_alloc_voter` (`voter_id`),
    CONSTRAINT `uq_voter_event_active`
        UNIQUE (`voter_id`, `event_id`, (CASE WHEN `status` IN ('CONFIRMED', 'CHECKED_IN') THEN 1 ELSE NULL END)),
    INDEX `idx_alloc_slot_status` (`slot_id`, `status`),
    INDEX `idx_alloc_token` (`booking_reference_token`),
    INDEX `idx_alloc_queue` (`slot_id`, `queue_token_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Voter time slot reservations and verification tokens';

-- ==============================================================================
-- TABLE 9: simulated_verifications
-- Privacy-safe simulated verification audit log.
-- Purely simulated mock tokens and simulated OTP/hash matches.
-- 3NF: Verification event depends solely on verification_id.
-- ==============================================================================
CREATE TABLE `simulated_verifications` (
    `verification_id` INT AUTO_INCREMENT PRIMARY KEY,
    `voter_id` INT NOT NULL,
    `booth_id` INT NOT NULL,
    `simulated_token` VARCHAR(64) NOT NULL,
    `verification_method` ENUM('SIMULATED_OTP', 'SIMULATED_EPIC_HASH', 'DEMO_BIOMETRIC_TOKEN') NOT NULL,
    `status` ENUM('PASSED', 'FAILED') NOT NULL DEFAULT 'PASSED',
    `failure_reason` VARCHAR(255) NULL,
    `verified_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_verif_voter`
        FOREIGN KEY (`voter_id`) REFERENCES `voters` (`voter_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_verif_booth`
        FOREIGN KEY (`booth_id`) REFERENCES `polling_booths` (`booth_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX `idx_verif_voter` (`voter_id`),
    INDEX `idx_verif_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Simulated demo verification records for voter authentication';

-- ==============================================================================
-- TABLE 10: crowd_telemetry
-- Real-time & historical crowd density sensor logs for ML feature extraction.
-- 3NF: Telemetry reading depends solely on telemetry_id.
-- ==============================================================================
CREATE TABLE `crowd_telemetry` (
    `telemetry_id` INT AUTO_INCREMENT PRIMARY KEY,
    `booth_id` INT NOT NULL,
    `slot_id` INT NOT NULL,
    `timestamp` DATETIME NOT NULL,
    `current_queue_length` INT NOT NULL DEFAULT 0,
    `avg_service_time_seconds` INT NOT NULL DEFAULT 120,
    `weather_condition` VARCHAR(50) NOT NULL DEFAULT 'CLEAR',
    `predicted_density_level` ENUM('LOW', 'MODERATE', 'HIGH', 'CRITICAL') NOT NULL DEFAULT 'LOW',
    `congestion_index` DECIMAL(5,2) NOT NULL DEFAULT 0.00 COMMENT 'Congestion scale 0.00 to 100.00',
    `recorded_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_telemetry_booth`
        FOREIGN KEY (`booth_id`) REFERENCES `polling_booths` (`booth_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT `fk_telemetry_slot`
        FOREIGN KEY (`slot_id`) REFERENCES `time_slots` (`slot_id`)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX `idx_telemetry_booth_time` (`booth_id`, `timestamp`),
    INDEX `idx_telemetry_density` (`predicted_density_level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Crowd density and queue metrics for ML model';

-- ==============================================================================
-- TABLE 11: os_concurrency_audit
-- OS Concurrency & Synchronization Audit Trail:
-- Tracks Mutex locks, Priority Aging, Starvation Prevention, and Deadlock Avoidance.
-- 3NF: Log entry depends solely on audit_id.
-- ==============================================================================
CREATE TABLE `os_concurrency_audit` (
    `audit_id` INT AUTO_INCREMENT PRIMARY KEY,
    `thread_name` VARCHAR(64) NOT NULL,
    `voter_id` INT NULL,
    `booth_id` INT NULL,
    `slot_id` INT NULL,
    `operation_type` ENUM('SLOT_LOCK', 'SLOT_RESERVE', 'LOCK_TIMEOUT', 'PRIORITY_ELEVATION', 'DEADLOCK_RESOLVED', 'ROLLBACK') NOT NULL,
    `lock_acquired_at` DATETIME(6) NULL,
    `lock_released_at` DATETIME(6) NULL,
    `status_code` VARCHAR(32) NOT NULL,
    `execution_latency_ms` DECIMAL(8,3) NOT NULL DEFAULT 0.000,
    `details` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_audit_thread` (`thread_name`),
    INDEX `idx_audit_operation` (`operation_type`),
    INDEX `idx_audit_status` (`status_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='OS Concurrency Engine transaction and locking log';

-- ==============================================================================
-- TRIGGERS FOR DATA INTEGRITY & ATOMIC CAPACITY UPDATES
-- ==============================================================================

DELIMITER $$

-- Trigger 1: Increment slot allocation count on new confirmed booking
CREATE TRIGGER `trg_after_allocation_insert`
AFTER INSERT ON `slot_allocations`
FOR EACH ROW
BEGIN
    IF NEW.status = 'CONFIRMED' THEN
        UPDATE `time_slots`
        SET `allocated_count` = `allocated_count` + 1,
            `status` = CASE
                WHEN `allocated_count` + 1 >= `max_capacity` THEN 'FULL'
                ELSE `status`
            END
        WHERE `slot_id` = NEW.slot_id;
    END IF;
END$$

-- Trigger 2: Recompute slot allocation count when status is changed (e.g. CANCELLED)
CREATE TRIGGER `trg_after_allocation_update`
AFTER UPDATE ON `slot_allocations`
FOR EACH ROW
BEGIN
    IF OLD.status = 'CONFIRMED' AND NEW.status IN ('CANCELLED', 'NO_SHOW') THEN
        UPDATE `time_slots`
        SET `allocated_count` = GREATEST(0, `allocated_count` - 1),
            `status` = CASE
                WHEN `status` = 'FULL' AND (`allocated_count` - 1) < `max_capacity` THEN 'OPEN'
                ELSE `status`
            END
        WHERE `slot_id` = NEW.slot_id;
    END IF;
END$$

DELIMITER ;

-- ==============================================================================
-- STORED PROCEDURES
-- Concurrency-Safe Stored Procedures with Explicit Row-Level Locking (ACID Compliant)
-- ==============================================================================

DELIMITER $$

-- Procedure 1: Concurrency-Safe Atomic Slot Allocation
-- Uses SELECT ... FOR UPDATE on time_slots to prevent race conditions & overbooking
DROP PROCEDURE IF EXISTS `sp_allocate_slot_atomic`$$
CREATE PROCEDURE `sp_allocate_slot_atomic`(
    IN  p_voter_id          INT,
    IN  p_booth_id          INT,
    IN  p_slot_id           INT,
    IN  p_allocation_type   VARCHAR(32),
    OUT p_status_code       VARCHAR(32),
    OUT p_booking_token     VARCHAR(64),
    OUT p_queue_token       INT
)
proc_block: BEGIN
    DECLARE v_voter_assigned_booth INT;
    DECLARE v_voter_priority       TINYINT;
    DECLARE v_event_id             INT;
    DECLARE v_slot_booth_id        INT;
    DECLARE v_max_capacity         INT;
    DECLARE v_allocated_count      INT;
    DECLARE v_priority_capacity    INT;
    DECLARE v_slot_status          VARCHAR(20);
    DECLARE v_existing_alloc_count INT DEFAULT 0;
    DECLARE v_generated_token      VARCHAR(64);
    DECLARE v_calculated_priority  INT DEFAULT 0;

    -- Error handler to guarantee rollback on SQLEXCEPTION
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code   = 'SQL_TRANSACTION_FAILED';
        SET p_booking_token = NULL;
        SET p_queue_token   = 0;
    END;

    -- Default output values
    SET p_status_code   = 'INITIALIZING';
    SET p_booking_token = NULL;
    SET p_queue_token   = 0;

    START TRANSACTION;

    -- 1. Validate voter existence, booth mapping, and priority
    SELECT `assigned_booth_id`, `priority_level`
    INTO v_voter_assigned_booth, v_voter_priority
    FROM `voters`
    WHERE `voter_id` = p_voter_id;

    IF v_voter_assigned_booth IS NULL THEN
        ROLLBACK;
        SET p_status_code = 'VOTER_NOT_FOUND';
        LEAVE proc_block;
    END IF;

    IF v_voter_assigned_booth <> p_booth_id THEN
        ROLLBACK;
        SET p_status_code = 'INVALID_BOOTH_JURISDICTION';
        LEAVE proc_block;
    END IF;

    -- 2. Validate slot existence & acquire EXCLUSIVE ROW LOCK (FOR UPDATE)
    SELECT `booth_id`, `event_id`, `max_capacity`, `allocated_count`, `priority_reserved_capacity`, `status`
    INTO v_slot_booth_id, v_event_id, v_max_capacity, v_allocated_count, v_priority_capacity, v_slot_status
    FROM `time_slots`
    WHERE `slot_id` = p_slot_id
    FOR UPDATE;

    IF v_slot_booth_id IS NULL THEN
        ROLLBACK;
        SET p_status_code = 'SLOT_NOT_FOUND';
        LEAVE proc_block;
    END IF;

    IF v_slot_booth_id <> p_booth_id THEN
        ROLLBACK;
        SET p_status_code = 'SLOT_MISMATCH_WITH_BOOTH';
        LEAVE proc_block;
    END IF;

    IF v_slot_status = 'CLOSED' THEN
        ROLLBACK;
        SET p_status_code = 'SLOT_CLOSED';
        LEAVE proc_block;
    END IF;

    -- 3. Check for existing active allocation for this voter in this election event
    SELECT COUNT(*)
    INTO v_existing_alloc_count
    FROM `slot_allocations`
    WHERE `voter_id` = p_voter_id
      AND `event_id` = v_event_id
      AND `status` IN ('CONFIRMED', 'CHECKED_IN');

    IF v_existing_alloc_count > 0 THEN
        ROLLBACK;
        SET p_status_code = 'DUPLICATE_BOOKING_PREVENTED';
        LEAVE proc_block;
    END IF;

    -- 4. Capacity and Priority Reservation Check
    -- If normal voter (priority > 1) and standard capacity reached, prevent booking
    IF v_voter_priority > 1 AND v_allocated_count >= v_max_capacity THEN
        ROLLBACK;
        SET p_status_code = 'SLOT_CAPACITY_EXCEEDED';
        LEAVE proc_block;
    END IF;

    -- If priority voter (priority == 1) but total emergency overflow quota exceeded
    IF v_voter_priority = 1 AND v_allocated_count >= (v_max_capacity + v_priority_capacity) THEN
        ROLLBACK;
        SET p_status_code = 'PRIORITY_CAPACITY_EXCEEDED';
        LEAVE proc_block;
    END IF;

    -- 5. Generate secure booking token & queue token
    SET v_generated_token     = CONCAT('TKN-UK-', p_slot_id, '-', UNIX_TIMESTAMP(), '-', LPAD(FLOOR(RAND() * 9999), 4, '0'));
    SET p_queue_token         = v_allocated_count + 1;
    SET v_calculated_priority = (4 - v_voter_priority) * 100;

    -- 6. Insert slot allocation record
    INSERT INTO `slot_allocations` (
        `voter_id`,
        `booth_id`,
        `slot_id`,
        `event_id`,
        `booking_reference_token`,
        `allocation_type`,
        `priority_score`,
        `queue_token_no`,
        `status`
    ) VALUES (
        p_voter_id,
        p_booth_id,
        p_slot_id,
        v_event_id,
        v_generated_token,
        IFNULL(p_allocation_type, 'USER_RESERVED'),
        v_calculated_priority,
        p_queue_token,
        'CONFIRMED'
    );

    -- Commit transaction (Trigger trg_after_allocation_insert will update allocated_count)
    COMMIT;

    SET p_status_code   = 'SUCCESS';
    SET p_booking_token = v_generated_token;

END proc_block$$

-- Procedure 2: Concurrency-Safe Atomic Slot Cancellation
DROP PROCEDURE IF EXISTS `sp_cancel_slot_atomic`$$
CREATE PROCEDURE `sp_cancel_slot_atomic`(
    IN  p_booking_token VARCHAR(64),
    OUT p_status_code   VARCHAR(32)
)
proc_block: BEGIN
    DECLARE v_alloc_id INT;
    DECLARE v_status   VARCHAR(20);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 'SQL_TRANSACTION_FAILED';
    END;

    START TRANSACTION;

    SELECT `allocation_id`, `status`
    INTO v_alloc_id, v_status
    FROM `slot_allocations`
    WHERE `booking_reference_token` = p_booking_token
    FOR UPDATE;

    IF v_alloc_id IS NULL THEN
        ROLLBACK;
        SET p_status_code = 'ALLOCATION_NOT_FOUND';
        LEAVE proc_block;
    END IF;

    IF v_status <> 'CONFIRMED' THEN
        ROLLBACK;
        SET p_status_code = 'CANNOT_CANCEL_NON_CONFIRMED';
        LEAVE proc_block;
    END IF;

    UPDATE `slot_allocations`
    SET `status` = 'CANCELLED'
    WHERE `allocation_id` = v_alloc_id;

    COMMIT;
    SET p_status_code = 'SUCCESS';

END proc_block$$

-- Procedure 3: Audit logging for OS Concurrency & Priority Scheduling Events
DROP PROCEDURE IF EXISTS `sp_log_os_concurrency_event`$$
CREATE PROCEDURE `sp_log_os_concurrency_event`(
    IN p_thread_name    VARCHAR(64),
    IN p_voter_id       INT,
    IN p_booth_id       INT,
    IN p_slot_id        INT,
    IN p_operation_type VARCHAR(32),
    IN p_status_code    VARCHAR(32),
    IN p_latency_ms     DECIMAL(8,3),
    IN p_details        TEXT
)
BEGIN
    INSERT INTO `os_concurrency_audit` (
        `thread_name`,
        `voter_id`,
        `booth_id`,
        `slot_id`,
        `operation_type`,
        `status_code`,
        `execution_latency_ms`,
        `details`
    ) VALUES (
        p_thread_name,
        p_voter_id,
        p_booth_id,
        p_slot_id,
        p_operation_type,
        p_status_code,
        p_latency_ms,
        p_details
    );
END$$

DELIMITER ;

-- ==============================================================================
-- DATABASE VIEWS FOR COMMAND DASHBOARDS & PASS GENERATION
-- ==============================================================================

-- VIEW 1: vw_booth_live_status
-- Real-time operational load and queue capacity across all booths and slots.
CREATE OR REPLACE VIEW `vw_booth_live_status` AS
SELECT
    b.booth_id,
    b.booth_number,
    b.booth_name,
    ps.station_id,
    ps.station_name,
    ps.address AS station_address,
    ps.pincode,
    pc.constituency_code AS pc_code,
    pc.constituency_name AS parliamentary_constituency,
    ac.constituency_code AS ac_code,
    ac.constituency_name AS assembly_constituency,
    ts.slot_id,
    ts.slot_date,
    ts.start_time,
    ts.end_time,
    ts.max_capacity,
    ts.allocated_count,
    GREATEST(0, (ts.max_capacity - ts.allocated_count)) AS available_capacity,
    ROUND((ts.allocated_count / ts.max_capacity) * 100, 2) AS capacity_utilization_pct,
    ts.status AS slot_status
FROM `polling_booths` b
JOIN `polling_stations` ps ON b.station_id = ps.station_id
JOIN `constituencies` pc ON b.pc_id = pc.constituency_id
JOIN `constituencies` ac ON b.ac_id = ac.constituency_id
JOIN `time_slots` ts ON b.booth_id = ts.booth_id
WHERE b.is_active = 1;

-- VIEW 2: vw_voter_appointment_slip
-- Formatted voter appointment pass details ready for digital pass / slip generation.
CREATE OR REPLACE VIEW `vw_voter_appointment_slip` AS
SELECT
    sa.allocation_id,
    sa.booking_reference_token,
    sa.queue_token_no,
    sa.status AS booking_status,
    sa.allocation_type,
    sa.booked_at,
    v.voter_id,
    v.demo_epic_no,
    v.full_name,
    v.gender,
    v.special_category,
    v.priority_level,
    b.booth_id,
    b.booth_number,
    b.booth_name,
    b.room_number,
    ps.station_id,
    ps.station_name,
    ps.address AS station_address,
    ps.pincode,
    ps.has_wheelchair_ramp,
    pc.constituency_name AS parliamentary_constituency,
    ac.constituency_name AS assembly_constituency,
    ts.slot_id,
    ts.slot_date,
    ts.start_time,
    ts.end_time,
    ee.event_name,
    ee.election_date
FROM `slot_allocations` sa
JOIN `voters` v ON sa.voter_id = v.voter_id
JOIN `polling_booths` b ON sa.booth_id = b.booth_id
JOIN `polling_stations` ps ON b.station_id = ps.station_id
JOIN `constituencies` pc ON b.pc_id = pc.constituency_id
JOIN `constituencies` ac ON b.ac_id = ac.constituency_id
JOIN `time_slots` ts ON sa.slot_id = ts.slot_id
JOIN `election_events` ee ON sa.event_id = ee.event_id;

-- VIEW 3: vw_constituency_logistics_summary
-- Executive analytics rollup for One Nation One Election logistics monitoring.
CREATE OR REPLACE VIEW `vw_constituency_logistics_summary` AS
SELECT
    c.constituency_id,
    c.constituency_code,
    c.constituency_name,
    c.constituency_type,
    s.state_name,
    c.total_registered_voters,
    COUNT(DISTINCT b.booth_id) AS total_booths,
    COUNT(DISTINCT ps.station_id) AS total_stations,
    COALESCE(SUM(ts.max_capacity), 0) AS total_slot_capacity,
    COALESCE(SUM(ts.allocated_count), 0) AS total_slots_allocated,
    CASE
        WHEN COALESCE(SUM(ts.max_capacity), 0) = 0 THEN 0.00
        ELSE ROUND((COALESCE(SUM(ts.allocated_count), 0) / SUM(ts.max_capacity)) * 100, 2)
    END AS aggregate_booking_pct
FROM `constituencies` c
JOIN `states` s ON c.state_id = s.state_id
LEFT JOIN `polling_booths` b ON (c.constituency_type = 'PARLIAMENTARY' AND b.pc_id = c.constituency_id)
                             OR (c.constituency_type = 'ASSEMBLY' AND b.ac_id = c.constituency_id)
LEFT JOIN `polling_stations` ps ON b.station_id = ps.station_id
LEFT JOIN `time_slots` ts ON b.booth_id = ts.booth_id
GROUP BY
    c.constituency_id,
    c.constituency_code,
    c.constituency_name,
    c.constituency_type,
    s.state_name,
    c.total_registered_voters;
