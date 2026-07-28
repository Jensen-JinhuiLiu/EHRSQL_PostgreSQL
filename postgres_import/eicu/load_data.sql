\set ON_ERROR_STOP on
BEGIN;
SET client_min_messages TO WARNING;
\copy allergy (allergyid, patientunitstayid, drugname, allergyname, allergytime) FROM '/tmp/ehrsql_import/eicu/csv/allergy.csv' WITH (FORMAT csv, NULL '\N')
\copy cost (costid, uniquepid, patienthealthsystemstayid, eventtype, eventid, chargetime, cost) FROM '/tmp/ehrsql_import/eicu/csv/cost.csv' WITH (FORMAT csv, NULL '\N')
\copy diagnosis (diagnosisid, patientunitstayid, diagnosisname, diagnosistime, icd9code) FROM '/tmp/ehrsql_import/eicu/csv/diagnosis.csv' WITH (FORMAT csv, NULL '\N')
\copy intakeoutput (intakeoutputid, patientunitstayid, cellpath, celllabel, cellvaluenumeric, intakeoutputtime) FROM '/tmp/ehrsql_import/eicu/csv/intakeoutput.csv' WITH (FORMAT csv, NULL '\N')
\copy lab (labid, patientunitstayid, labname, labresult, labresulttime) FROM '/tmp/ehrsql_import/eicu/csv/lab.csv' WITH (FORMAT csv, NULL '\N')
\copy medication (medicationid, patientunitstayid, drugname, dosage, routeadmin, drugstarttime, drugstoptime) FROM '/tmp/ehrsql_import/eicu/csv/medication.csv' WITH (FORMAT csv, NULL '\N')
\copy microlab (microlabid, patientunitstayid, culturesite, organism, culturetakentime) FROM '/tmp/ehrsql_import/eicu/csv/microlab.csv' WITH (FORMAT csv, NULL '\N')
\copy patient (uniquepid, patienthealthsystemstayid, patientunitstayid, gender, age, ethnicity, hospitalid, wardid, admissionheight, admissionweight, dischargeweight, hospitaladmittime, hospitaladmitsource, unitadmittime, unitdischargetime, hospitaldischargetime, hospitaldischargestatus) FROM '/tmp/ehrsql_import/eicu/csv/patient.csv' WITH (FORMAT csv, NULL '\N')
\copy treatment (treatmentid, patientunitstayid, treatmentname, treatmenttime) FROM '/tmp/ehrsql_import/eicu/csv/treatment.csv' WITH (FORMAT csv, NULL '\N')
\copy vitalperiodic (vitalperiodicid, patientunitstayid, temperature, sao2, heartrate, respiration, systemicsystolic, systemicdiastolic, systemicmean, observationtime) FROM '/tmp/ehrsql_import/eicu/csv/vitalperiodic.csv' WITH (FORMAT csv, NULL '\N')
COMMIT;
