-- Schema-only reference exported from PostgreSQL 18 on 2026-10-21.
-- For a NEW empty database only; never run over an existing database.
--
-- PostgreSQL database dump
--


-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: monitoring; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA monitoring;


--
-- Name: staging; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA staging;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: tube_lines; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.tube_lines (
    line_id character varying(100) NOT NULL,
    line_name character varying(150) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: tube_status_history; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.tube_status_history (
    status_id bigint NOT NULL,
    snapshot_time timestamp with time zone NOT NULL,
    line_id character varying(100) NOT NULL,
    status_severity integer NOT NULL,
    status_description character varying(200) NOT NULL,
    reason text,
    disruption_from timestamp with time zone,
    disruption_to timestamp with time zone,
    is_now boolean,
    source_file character varying(500),
    loaded_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tube_status_history_status_severity_check CHECK (((status_severity >= 0) AND (status_severity <= 20))),
    CONSTRAINT valid_disruption_period CHECK (((disruption_from IS NULL) OR (disruption_to IS NULL) OR (disruption_to >= disruption_from)))
);


--
-- Name: pipeline_runs; Type: TABLE; Schema: monitoring; Owner: -
--

CREATE TABLE monitoring.pipeline_runs (
    run_id uuid NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    status character varying(20) NOT NULL,
    failed_step character varying(100),
    error_message text,
    CONSTRAINT pipeline_runs_status_check CHECK (((status)::text = ANY ((ARRAY['RUNNING'::character varying, 'SUCCESS'::character varying, 'FAILED'::character varying])::text[]))),
    CONSTRAINT valid_run_times CHECK (((finished_at IS NULL) OR (finished_at >= started_at)))
);


--
-- Name: v_pipeline_run_health; Type: VIEW; Schema: monitoring; Owner: -
--

CREATE VIEW monitoring.v_pipeline_run_health AS
 SELECT run_id,
    started_at,
    finished_at,
    status,
        CASE
            WHEN (((status)::text = 'RUNNING'::text) AND (started_at < (now() - '00:15:00'::interval))) THEN 'STALE'::text
            WHEN ((status)::text = 'RUNNING'::text) THEN 'IN_PROGRESS'::text
            WHEN ((status)::text = 'SUCCESS'::text) THEN 'HEALTHY'::text
            WHEN ((status)::text = 'FAILED'::text) THEN 'FAILED'::text
            ELSE 'UNKNOWN'::text
        END AS health_status,
    round(EXTRACT(epoch FROM (COALESCE(finished_at, now()) - started_at)), 2) AS duration_seconds,
    failed_step,
    error_message
   FROM monitoring.pipeline_runs;


--
-- Name: tube_status_history_status_id_seq; Type: SEQUENCE; Schema: staging; Owner: -
--

ALTER TABLE staging.tube_status_history ALTER COLUMN status_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME staging.tube_status_history_status_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: pipeline_runs pipeline_runs_pkey; Type: CONSTRAINT; Schema: monitoring; Owner: -
--

ALTER TABLE ONLY monitoring.pipeline_runs
    ADD CONSTRAINT pipeline_runs_pkey PRIMARY KEY (run_id);


--
-- Name: tube_lines tube_lines_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.tube_lines
    ADD CONSTRAINT tube_lines_pkey PRIMARY KEY (line_id);


--
-- Name: tube_status_history tube_status_history_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.tube_status_history
    ADD CONSTRAINT tube_status_history_pkey PRIMARY KEY (status_id);


--
-- Name: idx_pipeline_runs_started; Type: INDEX; Schema: monitoring; Owner: -
--

CREATE INDEX idx_pipeline_runs_started ON monitoring.pipeline_runs USING btree (started_at DESC);


--
-- Name: idx_pipeline_runs_status; Type: INDEX; Schema: monitoring; Owner: -
--

CREATE INDEX idx_pipeline_runs_status ON monitoring.pipeline_runs USING btree (status);


--
-- Name: idx_tube_status_line_time; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX idx_tube_status_line_time ON staging.tube_status_history USING btree (line_id, snapshot_time DESC);


--
-- Name: idx_tube_status_snapshot; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX idx_tube_status_snapshot ON staging.tube_status_history USING btree (snapshot_time);


--
-- Name: uq_tube_status_snapshot; Type: INDEX; Schema: staging; Owner: -
--

CREATE UNIQUE INDEX uq_tube_status_snapshot ON staging.tube_status_history USING btree (snapshot_time, line_id, status_severity, status_description);


--
-- Name: tube_status_history tube_status_history_line_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.tube_status_history
    ADD CONSTRAINT tube_status_history_line_id_fkey FOREIGN KEY (line_id) REFERENCES staging.tube_lines(line_id);


--
-- PostgreSQL database dump complete
--


