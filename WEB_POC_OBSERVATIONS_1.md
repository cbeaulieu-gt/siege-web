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