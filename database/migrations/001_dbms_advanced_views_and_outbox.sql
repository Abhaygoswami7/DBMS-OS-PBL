-- ==============================================================================
-- MIGRATION 001: Advanced DBMS Views, Procedures & IPC Event Outbox Table
-- Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
-- ==============================================================================

USE `smart_poll_allocation_db`;

-- ------------------------------------------------------------------------------
-- 1. IPC EVENT OUTBOX TABLE (Guaranteed Event Delivery for Producer-Consumer)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `allocation_events_outbox` (
    `event_id` INT AUTO_INCREMENT PRIMARY KEY,
    `event_type` VARCHAR(64) NOT NULL COMMENT 'e.g. ALLOCATION_COMMITTED, ALLOCATION_CANCELLED, REALLOCATION_SWAPPED',
    `aggregate_id` VARCHAR(64) NOT NULL COMMENT 'e.g. booking_reference_token or voter_id',
    `payload_json` TEXT NOT NULL COMMENT 'Event state serialized as JSON',
    `status` ENUM('PENDING', 'PROCESSING', 'DELIVERED', 'FAILED') NOT NULL DEFAULT 'PENDING',
    `retry_count` INT NOT NULL DEFAULT 0,
    `error_message` TEXT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `processed_at` TIMESTAMP NULL,
    INDEX `idx_outbox_status_created` (`status`, `created_at`),
    INDEX `idx_outbox_aggregate` (`aggregate_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 2. ADVANCED DATABASE VIEWS (1NF/2NF/3NF Compliant)
-- ------------------------------------------------------------------------------

-- View 1: Available Polling Booths with Aggregated Capacity
CREATE OR REPLACE VIEW `vw_available_booths` AS
SELECT
    pb.booth_id,
    pb.station_id,
    ps.station_name,
    pb.booth_number,
    pb.booth_name,
    pb.room_number,
    pb.max_capacity_per_slot,
    ps.address,
    ps.latitude,
    ps.longitude,
    ps.has_wheelchair_ramp,
    pb.is_active,
    COALESCE(SUM(ts.max_capacity), 0) AS total_configured_capacity,
    COALESCE(SUM(ts.allocated_count), 0) AS total_allocated_seats,
    COALESCE(SUM(GREATEST(0, ts.max_capacity - ts.allocated_count)), 0) AS total_remaining_seats
FROM `polling_booths` pb
JOIN `polling_stations` ps ON pb.station_id = ps.station_id
LEFT JOIN `time_slots` ts ON pb.booth_id = ts.booth_id
WHERE pb.is_active = 1
GROUP BY pb.booth_id, pb.station_id, ps.station_name, pb.booth_number, pb.booth_name, pb.room_number,
         pb.max_capacity_per_slot, ps.address, ps.latitude, ps.longitude, ps.has_wheelchair_ramp, pb.is_active;

-- View 2: Booth Occupancy Breakdown by Special Priority Categories
CREATE OR REPLACE VIEW `vw_booth_occupancy` AS
SELECT
    pb.booth_id,
    pb.booth_name,
    ps.station_name,
    COUNT(sa.allocation_id) AS total_confirmed_bookings,
    SUM(CASE WHEN v.special_category = 'PREGNANT_WOMEN' THEN 1 ELSE 0 END) AS pregnant_women_count,
    SUM(CASE WHEN v.special_category = 'PERSON_WITH_DISABILITY' THEN 1 ELSE 0 END) AS pwd_count,
    SUM(CASE WHEN v.special_category = 'SENIOR_CITIZEN' THEN 1 ELSE 0 END) AS senior_citizen_count,
    SUM(CASE WHEN v.special_category = 'GENERAL' THEN 1 ELSE 0 END) AS general_voters_count
FROM `polling_booths` pb
JOIN `polling_stations` ps ON pb.station_id = ps.station_id
LEFT JOIN `slot_allocations` sa ON pb.booth_id = sa.booth_id AND sa.status IN ('CONFIRMED', 'CHECKED_IN')
LEFT JOIN `voters` v ON sa.voter_id = v.voter_id
GROUP BY pb.booth_id, pb.booth_name, ps.station_name;

-- View 3: Administrative Global Logistics Statistics
CREATE OR REPLACE VIEW `vw_administrative_statistics` AS
SELECT
    (SELECT COUNT(*) FROM `voters`) AS total_registered_voters,
    (SELECT COUNT(*) FROM `slot_allocations` WHERE `status` = 'CONFIRMED') AS total_confirmed_allocations,
    (SELECT COUNT(*) FROM `slot_allocations` WHERE `status` = 'CANCELLED') AS total_cancelled_allocations,
    (SELECT COUNT(*) FROM `polling_stations`) AS total_stations,
    (SELECT COUNT(*) FROM `polling_booths` WHERE `is_active` = 1) AS total_active_booths,
    (SELECT COUNT(*) FROM `time_slots` WHERE `status` = 'OPEN') AS total_open_slots,
    (SELECT COUNT(*) FROM `time_slots` WHERE `status` = 'FULL') AS total_full_slots,
    (SELECT COALESCE(SUM(`max_capacity`), 0) FROM `time_slots`) AS total_electoral_capacity,
    (SELECT COALESCE(SUM(`allocated_count`), 0) FROM `time_slots`) AS total_allocated_seats,
    (SELECT COUNT(*) FROM `os_concurrency_audit`) AS total_os_audit_events;

-- ------------------------------------------------------------------------------
-- 3. STORED PROCEDURES
-- ------------------------------------------------------------------------------

DELIMITER $$

-- Procedure 2: sp_check_booth_availability
-- Checks live slot occupancy and remaining seats for a given booth & election event
DROP PROCEDURE IF EXISTS `sp_check_booth_availability`$$
CREATE PROCEDURE `sp_check_booth_availability`(
    IN p_booth_id INT,
    IN p_event_id INT,
    OUT p_total_slots INT,
    OUT p_open_slots INT,
    OUT p_total_capacity INT,
    OUT p_total_allocated INT,
    OUT p_remaining_capacity INT
)
BEGIN
    SELECT
        COUNT(*),
        COALESCE(SUM(CASE WHEN `status` = 'OPEN' THEN 1 ELSE 0 END), 0),
        COALESCE(SUM(`max_capacity`), 0),
        COALESCE(SUM(`allocated_count`), 0),
        COALESCE(SUM(GREATEST(0, `max_capacity` - `allocated_count`)), 0)
    INTO
        p_total_slots,
        p_open_slots,
        p_total_capacity,
        p_total_allocated,
        p_remaining_capacity
    FROM `time_slots`
    WHERE `booth_id` = p_booth_id AND `event_id` = p_event_id;
END$$

-- Procedure 3: sp_generate_allocation_statistics
-- Returns aggregated category-wise allocation telemetry
DROP PROCEDURE IF EXISTS `sp_generate_allocation_statistics`$$
CREATE PROCEDURE `sp_generate_allocation_statistics`(
    IN p_event_id INT,
    OUT p_p1_count INT,
    OUT p_p2_count INT,
    OUT p_p3_count INT,
    OUT p_p4_count INT,
    OUT p_total_confirmed INT
)
BEGIN
    SELECT
        COALESCE(SUM(CASE WHEN v.`priority_level` = 1 THEN 1 ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN v.`priority_level` = 2 THEN 1 ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN v.`priority_level` = 3 THEN 1 ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN v.`priority_level` = 4 THEN 1 ELSE 0 END), 0),
        COUNT(sa.`allocation_id`)
    INTO
        p_p1_count,
        p_p2_count,
        p_p3_count,
        p_p4_count,
        p_total_confirmed
    FROM `slot_allocations` sa
    JOIN `voters` v ON sa.`voter_id` = v.`voter_id`
    WHERE sa.`event_id` = p_event_id AND sa.`status` = 'CONFIRMED';
END$$

DELIMITER ;
