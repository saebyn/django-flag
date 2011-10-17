--------------------------------------------
-- no south for now, just raw sql queries --
--------------------------------------------

----------------
-- 0.3 => 0.4 --
----------------

-- flag_flaggedcontent

-- update the status field from char to int
alter table flag_flaggedcontent alter status type smallint using cast(status as integer);
-- add a when_updated field
alter table flag_flaggedcontent add when_updated timestamp with time zone;
update flag_flaggedcontent as fc set when_updated=(select max(ff.when_added) from flag_flaginstance as ff where ff.flagged_content_id=fc.id);
alter table flag_flaggedcontent alter when_updated  set not null;

-- flag_flaginstance

-- remove the when_recalled field
alter table flag_flaginstance drop when_recalled;
-- add a status field
alter table flag_flaginstance add status smallint CHECK (status >= 0) default 1 not null;

