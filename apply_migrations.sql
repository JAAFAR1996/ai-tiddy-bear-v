-- 🎯 AI TEDDY BEAR DATABASE MIGRATIONS
-- تطبيق schema changes للنظام الجديد
-- تشغيل: psql -d ai_teddy_bear -f apply_migrations.sql

\echo '🚀 بدء تطبيق Database Migrations...'

-- المرحلة 1: إضافة is_active field للـ children table
\echo '📋 المرحلة 1: إضافة is_active field للـ children table'

-- التحقق من وجود العمود أولاً
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'children' AND column_name = 'is_active'
    ) THEN
        -- إضافة العمود
        ALTER TABLE children 
        ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL;
        
        -- إضافة index للأداء
        CREATE INDEX idx_children_is_active ON children(is_active);
        
        -- تحديث السجلات الموجودة
        UPDATE children SET is_active = TRUE WHERE is_active IS NULL;
        
        RAISE NOTICE 'تم إضافة is_active field بنجاح';
    ELSE
        RAISE NOTICE 'is_active field موجود مسبقاً';
    END IF;
END
$$;

-- المرحلة 2: إنشاء devices table
\echo '🛠️ المرحلة 2: إنشاء devices table'

-- التحقق من وجود الجدول أولاً
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'devices'
    ) THEN
        -- إنشاء devices table
        CREATE TABLE devices (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            
            -- Status and soft delete support
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            deleted_at TIMESTAMP WITH TIME ZONE,
            is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
            
            -- Data retention and compliance
            retention_status VARCHAR(32) DEFAULT 'active' NOT NULL,
            scheduled_deletion_at TIMESTAMP WITH TIME ZONE,
            
            -- Audit fields
            created_by UUID,
            updated_by UUID,
            
            -- Metadata
            metadata_json JSONB DEFAULT '{}' NOT NULL,
            
            -- Device identification
            device_id VARCHAR(64) UNIQUE NOT NULL,
            device_type VARCHAR(32) DEFAULT 'ESP32_TEDDY' NOT NULL,
            hardware_version VARCHAR(16),
            firmware_version VARCHAR(16),
            
            -- Device status and health
            status VARCHAR(32) DEFAULT 'pending' NOT NULL,
            last_seen_at TIMESTAMP WITH TIME ZONE,
            ip_address VARCHAR(45),
            
            -- Security credentials
            oob_secret VARCHAR(128),
            device_fingerprint VARCHAR(128),
            mac_address VARCHAR(17),
            
            -- Performance and monitoring
            cpu_usage_percent DECIMAL(5,2),
            memory_usage_percent DECIMAL(5,2),
            battery_level_percent DECIMAL(5,2),
            signal_strength_dbm INTEGER,
            
            -- Geographic information
            last_known_latitude DECIMAL(10,8),
            last_known_longitude DECIMAL(11,8),
            location_accuracy_meters DECIMAL(8,2),
            timezone_offset INTEGER,
            
            -- Operational data
            total_uptime_hours DECIMAL(10,2),
            last_restart_at TIMESTAMP WITH TIME ZONE,
            restart_reason VARCHAR(64),
            error_count INTEGER DEFAULT 0,
            
            -- Constraints
            CONSTRAINT valid_device_id CHECK (char_length(device_id) >= 3),
            CONSTRAINT valid_status CHECK (status IN ('pending', 'active', 'inactive', 'maintenance', 'error')),
            CONSTRAINT valid_device_type CHECK (device_type IN ('ESP32_TEDDY', 'RASPBERRY_PI', 'ANDROID', 'IOS')),
            CONSTRAINT valid_cpu_usage CHECK (cpu_usage_percent >= 0 AND cpu_usage_percent <= 100),
            CONSTRAINT valid_memory_usage CHECK (memory_usage_percent >= 0 AND memory_usage_percent <= 100),
            CONSTRAINT valid_battery_level CHECK (battery_level_percent >= 0 AND battery_level_percent <= 100)
        );
        
        -- إنشاء Indexes للأداء
        CREATE INDEX idx_devices_device_id ON devices(device_id);
        CREATE INDEX idx_devices_status ON devices(status);
        CREATE INDEX idx_devices_active_status ON devices(is_active, status);
        CREATE INDEX idx_devices_type ON devices(device_type);
        CREATE INDEX idx_devices_last_seen ON devices(last_seen_at DESC);
        CREATE INDEX idx_devices_created_at ON devices(created_at DESC);
        CREATE INDEX idx_devices_location ON devices(last_known_latitude, last_known_longitude);
        CREATE INDEX idx_devices_metadata_gin ON devices USING gin(metadata_json);
        
        -- إنشاء trigger لتحديث updated_at
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER update_devices_updated_at 
            BEFORE UPDATE ON devices 
            FOR EACH ROW 
            EXECUTE FUNCTION update_updated_at_column();
        
        RAISE NOTICE 'تم إنشاء devices table بنجاح';
    ELSE
        RAISE NOTICE 'devices table موجود مسبقاً';
    END IF;
END
$$;

-- المرحلة 3: التحقق من النتائج
\echo '✅ المرحلة 3: التحقق من النتائج'

-- عرض structure للـ children table
\echo '📋 Structure للـ children table:'
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'children' AND column_name = 'is_active'
ORDER BY ordinal_position;

-- عرض structure للـ devices table
\echo '🛠️ Structure للـ devices table:'
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'devices'
ORDER BY ordinal_position
LIMIT 10;

-- عرض الindexes المنشأة
\echo '📊 Indexes المنشأة:'
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes 
WHERE tablename IN ('children', 'devices') 
AND indexname LIKE '%active%' OR indexname LIKE '%device%'
ORDER BY tablename, indexname;

\echo '🎉 تم الانتهاء من تطبيق جميع Migrations بنجاح!'
\echo '🔗 الخطوة التالية: تحديث Claim API لاستخدام DeviceService'