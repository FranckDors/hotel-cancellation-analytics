-- sql/03_marts.sql
-- Analytics-ready tables built from staging.bookings_clean

CREATE SCHEMA IF NOT EXISTS mart;

-- One row per booking, with business-rule flags added
CREATE OR REPLACE TABLE mart.bookings_enriched AS
SELECT
    *,
    CASE
        WHEN lead_time <= 7   THEN '0-7 days'
        WHEN lead_time <= 30  THEN '8-30 days'
        WHEN lead_time <= 90  THEN '31-90 days'
        WHEN lead_time <= 180 THEN '91-180 days'
        ELSE '181+ days'
    END AS lead_time_bucket,
    COALESCE(lead_time > 180, FALSE)                                           AS is_long_lead_booking,
    COALESCE(is_repeated_guest = 1 AND previous_cancellations = 0, FALSE)      AS is_repeat_guest_safe,
    COALESCE(previous_cancellations > 0, FALSE)                                AS has_prior_cancellation
FROM staging.bookings_clean;

-- One row per agent (bookings with no agent are direct bookings and are excluded here)
CREATE OR REPLACE TABLE mart.agent_summary AS
WITH totals AS (
    SELECT
        COUNT(*)           AS all_bookings,
        SUM(is_canceled)   AS all_cancels,
        AVG(is_canceled)   AS overall_cancel_rate
    FROM staging.bookings_clean
),
per_agent AS (
    SELECT
        agent_id,
        COUNT(*)           AS bookings,
        SUM(is_canceled)   AS cancellations,
        AVG(is_canceled)   AS cancel_rate,
        AVG(lead_time)     AS avg_lead_time,
        AVG(adr)           AS avg_adr,
        AVG(total_nights)  AS avg_nights,
        AVG(CASE WHEN deposit_type = 'No Deposit' THEN 1.0 ELSE 0.0 END) AS share_no_deposit
    FROM staging.bookings_clean
    WHERE agent_id IS NOT NULL
    GROUP BY agent_id
)
SELECT
    p.agent_id,
    p.bookings,
    p.cancellations,
    p.cancel_rate,
    p.avg_lead_time,
    p.avg_adr,
    p.avg_nights,
    p.share_no_deposit,
    p.bookings * 1.0 / t.all_bookings        AS share_of_all_bookings,
    p.cancellations * 1.0 / t.all_cancels    AS share_of_all_cancellations,
    t.overall_cancel_rate,
    (p.bookings >= 100 AND p.cancel_rate >= t.overall_cancel_rate + 0.10) AS is_high_cancel_agent,
    RANK() OVER (ORDER BY p.bookings DESC)       AS rank_by_bookings,
    RANK() OVER (ORDER BY p.cancellations DESC)  AS rank_by_cancellations
FROM per_agent p
CROSS JOIN totals t;