Initial building seed on creating new Siege
Drag and drop member on board would be nice functionality
Leveling up buildings doesnt seem to do anything
board should either allow reordering columns or at least have a different fixed order
Buildings are always static. No need for adding/removing buildings.
Member Sort Value needs an explanation or string to int mapping
Member name dropdowns on board doesnt show member name
Member board doesnt show member name
Lifecycle buttons are confusing. Needs clearer mapping to Planning/Start/Closed
Defense scroll count should be a calculated value based on # of defense slots
No options in UI to see Post Condition list
Can't set Post conditions for Siege In UI
Can't set Preferred Post Conditions for Members in UI
Post Priority should be Low, Medium, High - not an integer value
New members added during a Siege planning period should be availible for assignment during that siege
There cannot be more than 30 active members at any time
Attack Day Preview shows Member ID instead of Member Name
Attack Day Preview Apply button doesnt work - returns 409 CONFLICT
Board is messy. Should separate into Building/Post Views (same page) as posts only ever have a single assignment

=========================================

Lets change the level int field to a series of horizontal buttons with the range 1-6, which are the only valid levels for a building
Move the description of the post to be global as well and show the description text in the post field in the Siege
On the Board page I should be able to see a per member count of assignments so i can easily validate if i have exceeded per member scroll assignment

================== Post Condition Issues =======================

The following items needs to be addressed

  - A way to view all the post conditions 
    - Just needs to be a well formatted static table for reference
  - A way to set the Post Conditions for each post during a Siege
    - The Save Conditions button is there but there are no selection prompts
  - A way to set the Preferred Post Conditions for a Member
    - This is completely missing from the front-end

=============================================================================

- Sort Value is confusing. It should be removed and we should sort alphabetically by default
  with per user overrides
- Member Power should ranges not an integer
  - Less than 10mil
  - 10-15 mil
  - 16-20 mil
  - 21-25 mil
  - Greater than 25 mil
- Ideally can filter the post conditions by text to make selection easier. Is there a better interface to display this
- Member display in Board should color code members by definable conditions
    - Role
    - Power Level
- When closed the member board should not be editable. Same for Mebers and settings. Either lock the elements
  from editing or at least show in red on every page that the Siege is locked
  - The request is rejected but its unclear why to the user. It appears to be an error not an invalid action
- Same for Members and Settings. 
- When setting members to a position in the board it would be nice to be able to view a small summary of their information, e.g. Role/Power

===========================================================

- Lets merge the two posts top level tabs into a single Posts tab and then have sub sections
- Lets import and seed the following by pulling the most recent copy from the excel documents
  - Member Power Levels
  - Member Roles
  - Post Descriptions
  - Mark members inactive if they werent present in the most recent siege

============================================================

- 500 error trying to downgrade building level during siege
- 400 error trying to start siege with invalid conditions. Show error message regarding Validtion instead of just Failure
- Defense scroll count calculation is wrong. Its should be calculated from all Defense slots regardless of type. Does not depend on # of active siege members

================================

- 500 error trying to Delete siege
- 500 error trying to set Stronghold to level 6
- Make the defense  scroll count update live so when the building levels change the count is refreshed instantly
- Move discord buttons to the top

================================

- Make the siege button horizontal instead of vertically aligned
- COnfirm on Clone siege button
- Adds scrolls per member next to Defense Scroll count as a dynamically generated field

========================================

- Color code members as

  Heavy Hitter - Red
  Advanced - Gold/Yellow
  Medium - Green
  Novice Blue

- When a member has more assignments than num defense scrolls the selection on the side should highlight that row as invalid
- There needs to be a way to assign a RESERVE slot to a post. Currently you have to set a member
- When you click Edit Condition on a post in the Board it should expand the same post in the Posts page
- Preview auto fill shows a 500 internal server error
- When dragging from the Member selection sometimes a horizontal scrollbar appears and the element scrolls the members out of the primary window

======================================

- Add a toggle to show diffs only on the comparison page
- Setting Post conditions returns a 422 error {"detail":"Method Not Allowed"}
- Show # of Post conditions in Bar so its easy to tell what posts have conditions 
- When the Stronghold Board has 2 rows the row spanner does not fill the entire element

======================================

- Posts Tab no longer shows on Board Page
- Add a drop down filter in the Members selection to filter by Role
- The vertical alighment of the Members element moves downward slightly when any Post is expanded

========================================

Make the Dicord Notitifactions button align horizontally instead of vertical stacking
Move the Lifecycle above the Discord Notification section
The validation display shows Member_Id instead of member name

=======================================================

Disable discord notifications buttons on Closed Sieges
The Siege tab buttons change positions with the body of the page. They should be locked at the top in a static position
Make the Stronhold Buildings Field collapsable as well
Add a Auto-Assign Reserve Button which flags all Day 2 Attackers to set reserves
Add the Role of the Member on the Members page