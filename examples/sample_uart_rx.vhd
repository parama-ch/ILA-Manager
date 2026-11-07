library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.axis_pkg.all;

entity sample_uart_rx is
    generic (
        CLKS_PER_BIT : integer := 868;  -- 100MHz / 115200 baud
        FIFO_DEPTH   : integer := 4
    );
    port (
        clk         : in  std_logic;
        rst_n       : in  std_logic;
        rx_serial   : in  std_logic;
        rx_byte     : out std_logic_vector(7 downto 0);
        rx_valid    : out std_logic;
        rx_error    : out std_logic
    );
end entity sample_uart_rx;

architecture rtl of sample_uart_rx is
    type state_t is (s_idle, s_start, s_data, s_stop, s_cleanup);
    signal state : state_t := s_idle;

    signal clk_count   : integer range 0 to CLKS_PER_BIT - 1 := 0;
    signal bit_index   : integer range 0 to 7 := 0;
    signal rx_byte_reg : std_logic_vector(7 downto 0) := (others => '0');
    signal rx_data_r   : std_logic := '1';
    signal rx_data     : std_logic := '1';

    signal fifo_mem    : byte_buffer_t;
    signal m_axis      : axis_stream_t;
    signal packet_cnt  : unsigned(15 downto 0) := (others => '0');
begin
    -- Double register the serial input to prevent metastability
    p_sync : process (clk)
    begin
        if rising_edge(clk) then
            rx_data_r <= rx_serial;
            rx_data   <= rx_data_r;
        end if;
    end process p_sync;

    -- UART RX State Machine
    p_uart_rx : process (clk, rst_n)
    begin
        if rst_n = '0' then
            state       <= s_idle;
            rx_valid    <= '0';
            rx_error    <= '0';
            clk_count   <= 0;
            bit_index   <= 0;
            packet_cnt  <= (others => '0');
        elsif rising_edge(clk) then
            case state is
                when s_idle =>
                    rx_valid  <= '0';
                    rx_error  <= '0';
                    clk_count <= 0;
                    bit_index <= 0;
                    if rx_data = '0' then  -- Start bit detected
                        state <= s_start;
                    end if;

                when s_start =>
                    if clk_count = (CLKS_PER_BIT - 1) / 2 then
                        if rx_data = '0' then
                            clk_count <= 0;
                            state     <= s_data;
                        else
                            state <= s_idle;
                        end if;
                    else
                        clk_count <= clk_count + 1;
                    end if;

                when s_data =>
                    if clk_count < CLKS_PER_BIT - 1 then
                        clk_count <= clk_count + 1;
                    else
                        clk_count <= 0;
                        rx_byte_reg(bit_index) <= rx_data;
                        if bit_index < 7 then
                            bit_index <= bit_index + 1;
                        else
                            bit_index <= 0;
                            state     <= s_stop;
                        end if;
                    end if;

                when s_stop =>
                    if clk_count < CLKS_PER_BIT - 1 then
                        clk_count <= clk_count + 1;
                    else
                        rx_valid   <= '1';
                        clk_count  <= 0;
                        state      <= s_cleanup;
                        packet_cnt <= packet_cnt + 1;
                    end if;

                when s_cleanup =>
                    state    <= s_idle;
                    rx_valid <= '0';

                when others =>
                    state <= s_idle;
            end case;
        end if;
    end process p_uart_rx;

    rx_byte <= rx_byte_reg;

end architecture rtl;
