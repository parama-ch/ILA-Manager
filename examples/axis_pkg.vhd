library ieee;
use ieee.std_logic_1164.all;

package axis_pkg is
    constant C_AXI_DATA_W : integer := 32;

    type axis_stream_t is record
        tdata  : std_logic_vector(C_AXI_DATA_W-1 downto 0);
        tkeep  : std_logic_vector(3 downto 0);
        tvalid : std_logic;
        tlast  : std_logic;
    end record;

    type byte_buffer_t is array (0 to 3) of std_logic_vector(7 downto 0);
end package axis_pkg;
