-- Database yaratish
CREATE DATABASE mahalla_bot;

-- Kontaktlar jadvali
CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    service TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL,
    click_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Click count uchun index
CREATE INDEX IF NOT EXISTS idx_contacts_click_count
ON contacts(click_count DESC);

-- Demo ma'lumotlar
INSERT INTO contacts (service, phone) VALUES
('Tez yordam', '103'),
('Temir yo‘l', '105'),
('Elektrik xizmati', '998901234567'),
('Suv xizmati', '998902345678'),
('Gaz xizmati', '998903456789')
ON CONFLICT (service) DO NOTHING;