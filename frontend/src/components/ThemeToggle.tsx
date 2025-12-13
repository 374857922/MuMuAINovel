import { Button, Tooltip } from 'antd';
import { MoonOutlined, SunOutlined } from '@ant-design/icons';
import { useThemeStore } from '../store/themeStore';

interface ThemeToggleProps {
    style?: React.CSSProperties;
    className?: string;
}

export default function ThemeToggle({ style, className }: ThemeToggleProps) {
    const { isDarkMode, toggleTheme } = useThemeStore();

    return (
        <Tooltip title={isDarkMode ? '切换到日间模式' : '切换到夜间模式'}>
            <Button
                type="text"
                icon={isDarkMode ? <SunOutlined /> : <MoonOutlined />}
                onClick={toggleTheme}
                style={{
                    color: isDarkMode ? '#ffd700' : '#667eea',
                    fontSize: '18px',
                    ...style,
                }}
                className={className}
            />
        </Tooltip>
    );
}
