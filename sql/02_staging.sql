-- sql/02_staging.sql
-- Builds staging.bookings_typed (all rows, typed, with problem flags)
-- and staging.bookings_clean (typed rows minus the clearly bad ones).

CREATE SCHEMA IF NOT EXISTS staging;

CREATE OR REPLACE TABLE staging.bookings_typed AS
WITH converted AS (
    SELECT
        hotel,
        TRY_CAST(is_canceled AS INTEGER)                  AS is_canceled,
        TRY_CAST(lead_time AS INTEGER)                    AS lead_time,
        TRY_CAST(arrival_date_year AS INTEGER)            AS arrival_year,
        CASE TRIM(arrival_date_month)
            WHEN 'January' THEN 1   WHEN 'February' THEN 2
            WHEN 'March' THEN 3     WHEN 'April' THEN 4
            WHEN 'May' THEN 5       WHEN 'June' THEN 6
            WHEN 'July' THEN 7      WHEN 'August' THEN 8
            WHEN 'September' THEN 9 WHEN 'October' THEN 10
            WHEN 'November' THEN 11 WHEN 'December' THEN 12
        END                                               AS arrival_month,
        TRY_CAST(arrival_date_day_of_month AS INTEGER)    AS arrival_day,
        TRY_CAST(stays_in_weekend_nights AS INTEGER)      AS weekend_nights,
        TRY_CAST(stays_in_week_nights AS INTEGER)         AS week_nights,
        TRY_CAST(adults AS INTEGER)                       AS adults,
        -- children is missing for a handful of rows, so treat missing as 0
        COALESCE(TRY_CAST(TRY_CAST(children AS DOUBLE) AS INTEGER), 0) AS children,
        COALESCE(TRY_CAST(babies AS INTEGER), 0)          AS babies,
        meal,
        -- the text 'NULL' is not a real blank, so convert it
        COALESCE(NULLIF(NULLIF(TRIM(country), 'NULL'), 'NA'), 'Unknown') AS country,
        market_segment,
        distribution_channel,
        TRY_CAST(is_repeated_guest AS INTEGER)            AS is_repeated_guest,
        TRY_CAST(previous_cancellations AS INTEGER)       AS previous_cancellations,
        TRY_CAST(previous_bookings_not_canceled AS INTEGER) AS previous_bookings_not_canceled,
        reserved_room_type,
        assigned_room_type,
        TRY_CAST(booking_changes AS INTEGER)              AS booking_changes,
        deposit_type,
        NULLIF(NULLIF(TRIM(agent), 'NULL'), 'NA')         AS agent_id,
        (NULLIF(NULLIF(TRIM(company), 'NULL'), 'NA') IS NOT NULL) AS has_company,
        TRY_CAST(days_in_waiting_list AS INTEGER)         AS days_in_waiting_list,
        customer_type,
        TRY_CAST(adr AS DOUBLE)                           AS adr,
        TRY_CAST(required_car_parking_spaces AS INTEGER)  AS required_car_parking_spaces,
        TRY_CAST(total_of_special_requests AS INTEGER)    AS total_of_special_requests,
        reservation_status,   -- WARNING: reveals the outcome, never use as a model feature
        TRY_CAST(reservation_status_date AS DATE)         AS reservation_status_date
    FROM raw.hotel_bookings
),
derived AS (
    SELECT
        *,
        TRY_CAST(printf('%04d-%02d-%02d', arrival_year, arrival_month, arrival_day) AS DATE) AS arrival_date,
        COALESCE(weekend_nights, 0) + COALESCE(week_nights, 0)  AS total_nights,
        COALESCE(adults, 0) + children + babies                 AS total_guests,
        (agent_id IS NOT NULL)                                  AS has_agent
    FROM converted
)
SELECT
    ROW_NUMBER() OVER ()  AS booking_id,
    *,
    COALESCE(total_guests = 0, FALSE)  AS is_zero_guests,
    COALESCE(adr < 0, FALSE)           AS is_negative_adr,
    (is_canceled IS NULL OR lead_time IS NULL OR arrival_date IS NULL OR adr IS NULL) AS is_missing_key_field,
    (total_nights = 0)                 AS is_zero_nights
FROM derived;

CREATE OR REPLACE TABLE staging.bookings_clean AS
SELECT * EXCLUDE (is_zero_guests, is_negative_adr, is_missing_key_field)
FROM staging.bookings_typed
WHERE NOT is_zero_guests
  AND NOT is_negative_adr
  AND NOT is_missing_key_field;