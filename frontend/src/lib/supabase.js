import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://ybyqobdyvbmsiehdmxwp.supabase.co'
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlieXFvYmR5dmJtc2llaGRteHdwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjcxMTk0OTksImV4cCI6MjA4MjY5NTQ5OX0.SFMy7R1Bswe0X3ub2lcVfRMsgRhFl-gBmudPHoenBxk'

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
