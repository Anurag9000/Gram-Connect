/*
  # Gram-Connect Schema

  This migration creates the database structure for the Gram-Connect platform,
  which matches village problems with volunteer skills.

  ## New Tables

  1. `profiles`
     - Extends auth.users with role-based information
     - `id` (uuid, primary key, references auth.users)
     - `email` (text)
     - `full_name` (text)
     - `phone` (text)
     - `role` (text: 'villager', 'volunteer', 'coordinator')
     - `created_at` (timestamptz)

  2. `volunteers`
     - Stores volunteer-specific information
     - `id` (uuid, primary key)
     - `user_id` (uuid, references profiles)
     - `skills` (text array)
     - `availability_status` (text: 'available', 'busy', 'inactive')
     - `created_at` (timestamptz)

  3. `problems`
     - Stores problems submitted by villagers
     - `id` (uuid, primary key)
     - `villager_id` (uuid, references profiles)
     - `title` (text)
     - `description` (text)
     - `category` (text: 'education', 'health', 'infrastructure', 'digital', 'others')
     - `village_name` (text)
     - `status` (text: 'pending', 'in_progress', 'completed')
     - `created_at` (timestamptz)
     - `updated_at` (timestamptz)

  4. `matches`
     - Links problems with assigned volunteers
     - `id` (uuid, primary key)
     - `problem_id` (uuid, references problems)
     - `volunteer_id` (uuid, references volunteers)
     - `assigned_at` (timestamptz)
     - `completed_at` (timestamptz, nullable)
     - `notes` (text)

  ## Security

  - Enable RLS on all tables
  - Profiles: Users can read all profiles, update only their own
  - Volunteers: All authenticated users can read, volunteers can update their own
  - Problems: Authenticated users can read all, villagers can create and update their own
  - Matches: Coordinators can create/update, all authenticated users can read
*/

CREATE TABLE IF NOT EXISTS profiles (
  id uuid PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE,
  email text UNIQUE NOT NULL,
  full_name text NOT NULL,
  phone text,
  role text NOT NULL CHECK (role IN ('villager', 'volunteer', 'coordinator')),
  created_at timestamptz DEFAULT now()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read profiles"
  ON profiles FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Users can update own profile"
  ON profiles FOR UPDATE
  TO authenticated
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can insert own profile"
  ON profiles FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = id);

CREATE TABLE IF NOT EXISTS volunteers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
  skills text[] DEFAULT '{}',
  availability_status text DEFAULT 'available' CHECK (availability_status IN ('available', 'busy', 'inactive')),
  created_at timestamptz DEFAULT now(),
  UNIQUE(user_id)
);

ALTER TABLE volunteers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read volunteers"
  ON volunteers FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Volunteers can update own record"
  ON volunteers FOR UPDATE
  TO authenticated
  USING (user_id IN (SELECT id FROM profiles WHERE id = auth.uid() AND role = 'volunteer'))
  WITH CHECK (user_id IN (SELECT id FROM profiles WHERE id = auth.uid() AND role = 'volunteer'));

CREATE POLICY "Volunteers can insert own record"
  ON volunteers FOR INSERT
  TO authenticated
  WITH CHECK (user_id IN (SELECT id FROM profiles WHERE id = auth.uid() AND role = 'volunteer'));

CREATE TABLE IF NOT EXISTS problems (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  villager_id uuid REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
  title text NOT NULL,
  description text NOT NULL,
  category text NOT NULL CHECK (category IN ('education', 'health', 'infrastructure', 'digital', 'others')),
  village_name text NOT NULL,
  status text DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE problems ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read problems"
  ON problems FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Villagers can insert problems"
  ON problems FOR INSERT
  TO authenticated
  WITH CHECK (villager_id IN (SELECT id FROM profiles WHERE id = auth.uid() AND role = 'villager'));

CREATE POLICY "Villagers can update own problems"
  ON problems FOR UPDATE
  TO authenticated
  USING (villager_id = auth.uid())
  WITH CHECK (villager_id = auth.uid());

CREATE POLICY "Coordinators can update any problem"
  ON problems FOR UPDATE
  TO authenticated
  USING (auth.uid() IN (SELECT id FROM profiles WHERE role = 'coordinator'))
  WITH CHECK (auth.uid() IN (SELECT id FROM profiles WHERE role = 'coordinator'));

CREATE TABLE IF NOT EXISTS matches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  problem_id uuid REFERENCES problems(id) ON DELETE CASCADE NOT NULL,
  volunteer_id uuid REFERENCES volunteers(id) ON DELETE CASCADE NOT NULL,
  assigned_at timestamptz DEFAULT now(),
  completed_at timestamptz,
  notes text,
  UNIQUE(problem_id, volunteer_id)
);

ALTER TABLE matches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read matches"
  ON matches FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Coordinators can insert matches"
  ON matches FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() IN (SELECT id FROM profiles WHERE role = 'coordinator'));

CREATE POLICY "Coordinators can update matches"
  ON matches FOR UPDATE
  TO authenticated
  USING (auth.uid() IN (SELECT id FROM profiles WHERE role = 'coordinator'))
  WITH CHECK (auth.uid() IN (SELECT id FROM profiles WHERE role = 'coordinator'));

CREATE POLICY "Volunteers can update their matches"
  ON matches FOR UPDATE
  TO authenticated
  USING (volunteer_id IN (SELECT id FROM volunteers WHERE user_id = auth.uid()))
  WITH CHECK (volunteer_id IN (SELECT id FROM volunteers WHERE user_id = auth.uid()));

CREATE INDEX IF NOT EXISTS idx_problems_status ON problems(status);
CREATE INDEX IF NOT EXISTS idx_problems_category ON problems(category);
CREATE INDEX IF NOT EXISTS idx_problems_villager ON problems(villager_id);
CREATE INDEX IF NOT EXISTS idx_volunteers_user ON volunteers(user_id);
CREATE INDEX IF NOT EXISTS idx_matches_problem ON matches(problem_id);
CREATE INDEX IF NOT EXISTS idx_matches_volunteer ON matches(volunteer_id);
